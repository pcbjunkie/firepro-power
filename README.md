# firepro-power

Raise the chip power limit of **AMD FirePro** GPUs on Linux at runtime, and pin their clocks, with **no VBIOS
flash**. It loads a patched copy of each card's own PowerPlay table through
amdgpu's `/sys/class/drm/cardN/device/pp_table`, so a reboot always brings back the stock limits.

Developed on the **FirePro S7150 / S7150 x2** (Tonga, GCN3), which ships with an **81 W** chip limit, and under sustained compute it throttles hard on it: on LLM prompt
processing the GPUs sat at 849 MHz instead of their 920 MHz top clock. Raising the limit gave:

| llama.cpp, Qwen3-30B-A3B, 4x S7150 | 81 W (stock) | 100 W |
|---|---|---|
| prompt processing, short context | baseline | +12% |
| prompt processing, 16K context | baseline | +22% |
| token generation | baseline | unchanged |

Token generation never reached the limit, so it doesn't gain. Pinning clocks (`dpm high`) also matters on
multi-GPU setups: on `auto`, each GPU drops clocks by a different amount, so they reach synchronization points
at different times.

Developed for [llama.cpp-radeon-firepro](https://github.com/pcbjunkie/llama.cpp-radeon-firepro).

## ⚠️ Read this first

Running a GPU above its rated power limit is **at your own risk**. The numbers above were measured in a Dell
R720 with server fans at full airflow, where four S7150s at 110 W pulled about 960 W at the wall. These are
passively cooled cards: in a desktop case or a chassis without strong front-to-back airflow they will overheat.
Watch the temperatures (`firepro-power show`) and your power supply's headroom.

Dual-GPU boards share one power budget: an S7150 x2 is rated about 265 W for the whole board, so two GPUs at 110 W
run close to it, which stresses the board's voltage regulators more than stock. 100 W gives most of the gain.

The tool can't brick a card: it never writes the VBIOS. A bad table can at worst hang the GPU until a reboot,
which restores the stock table. Thermal limits are left untouched. Limits above stock + 35% (81 -> 110 W on the
S7150) need `--unsafe`, which allows up to stock + 85%.

## Install

```
git clone https://github.com/pcbjunkie/firepro-power && cd firepro-power
sudo ./install.sh            # installs /usr/local/sbin/firepro-power
sudo ./install.sh --enable   # ... and applies /etc/default/firepro-power at every boot
```

Requires the `amdgpu` kernel driver (tested on Debian 12, kernel 6.1), `python3` and `fuser` (psmisc). It can
also run straight from the clone: `sudo ./firepro-power ...`.

## Usage

```
firepro-power show                         # limits, power, temperature and clocks of every card
sudo firepro-power set 110                 # 110 W chip limit on all S7150s
sudo firepro-power set 100 card1 card2     # ... or on some of them
sudo firepro-power dpm high                # pin the top clocks (auto: back to the driver)
sudo firepro-power stock                   # the original table again
```

Load a table only while nothing runs on the GPUs: the driver re-initializes power management when it gets one.
If processes merely hold the device files open (a desktop compositor, logind), `--force` goes ahead anyway.

The boot service (`firepro-power.service`) reads `/etc/default/firepro-power` (`WATTS=110`, `DPM=high`, `CARDS=`)
and runs before the display manager.

## How it works

The first time a card is touched after boot, its PowerPlay table is saved to `/run/firepro-power/` (that is the
stock table, since `/run` is emptied at boot). Each `set` patches that copy, sets the PowerTune `TDP`,
`ConfigurableTDP` and `MaximumPowerDeliveryLimit` to the new watts and scales the current limit (`TDC`) to
match, then writes it back to the card. `pptable.py dump <file>` decodes a table, e.g. the live one at
`/sys/class/drm/card1/device/pp_table`.

## Supported cards

The tool only touches PowerPlay tables in the Tonga format (revision 7) and ignores every other GPU.

| family | cards (examples) | status |
|---|---|---|
| Tonga (GCN3) | FirePro S7150, S7150 x2 | tested |
| Tonga (GCN3) | FirePro S7100X, W7100 | same table format, untested |
| Fiji, Polaris | FirePro S9300 x2, Radeon Pro WX 4100-7100 | same table format, untested |
| Hawaii (GCN2) | FirePro W9100, S9150 | probably not: the older power code amdgpu uses for these has no `pp_table` file |
| Vega and newer | Radeon Pro WX 9100, ... | different table format, not supported yet |

If you try it on an untested card, `pptable.py dump /sys/class/drm/cardN/device/pp_table` shows what it reads.
Please report what you find.

## Adding a card family

Support for more generations (Vega and newer) is planned, as cards become available to test. Most of the tool
doesn't depend on the card: the stock-table capture, limits relative to stock, busy check, clock pinning and the
boot service work unchanged. A new family needs:

1. a dump of its table: `cat /sys/class/drm/cardN/device/pp_table > card.bin` (plus the card's name and
   `cat /sys/class/drm/cardN/device/device`)
2. its layout in `pptable.py`, from the matching header in the kernel source
   (`drivers/gpu/drm/amd/pm/powerplay/hwmgr/*_pptable.h`): which bytes hold the power limits
3. a test on a real card: `show` reports the new limit and clocks rise under load, then `stock` restores it

Until a format is added, the tool leaves those cards alone.
