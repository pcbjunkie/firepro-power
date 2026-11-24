#!/usr/bin/env python3
# Decode (and optionally patch) a Tonga (GCN3) PowerPlay table as exposed by amdgpu in
# /sys/class/drm/cardN/device/pp_table. Layout from linux drivers/gpu/drm/amd/pm/powerplay/hwmgr/tonga_pptable.h.
# usage: pptable.py dump <file>
#        pptable.py get <file> <field> ...       (prints the values, one per line; header or PowerTune fields)
#        pptable.py patch <in> <out> [tdp=W] [tdc=A] [maxpower=W] [powercontrol=%]
import struct, sys

HDR = [  # ATOM_Tonga_POWERPLAYTABLE, packed
    ('usStructureSize', 'H'), ('ucTableFormatRevision', 'B'), ('ucTableContentRevision', 'B'),
    ('ucTableRevision', 'B'), ('usTableSize', 'H'), ('ulGoldenPPID', 'I'), ('ulGoldenRevision', 'I'),
    ('usFormatID', 'H'), ('usVoltageTime', 'H'), ('ulPlatformCaps', 'I'), ('ulMaxODEngineClock', 'I'),
    ('ulMaxODMemoryClock', 'I'), ('usPowerControlLimit', 'H'), ('usUlvVoltageOffset', 'H'),
    ('usStateArrayOffset', 'H'), ('usFanTableOffset', 'H'), ('usThermalControllerOffset', 'H'), ('usReserv', 'H'),
    ('usMclkDependencyTableOffset', 'H'), ('usSclkDependencyTableOffset', 'H'), ('usVddcLookupTableOffset', 'H'),
    ('usVddgfxLookupTableOffset', 'H'), ('usMMDependencyTableOffset', 'H'), ('usVCEStateTableOffset', 'H'),
    ('usPPMTableOffset', 'H'), ('usPowerTuneTableOffset', 'H'), ('usHardLimitTableOffset', 'H'),
    ('usPCIETableOffset', 'H'), ('usGPIOTableOffset', 'H'),
]
POWERTUNE = [  # ATOM_Tonga_PowerTune_Table (rev 0); later revisions append fields
    ('ucRevId', 'B'), ('usTDP', 'H'), ('usConfigurableTDP', 'H'), ('usTDC', 'H'), ('usBatteryPowerLimit', 'H'),
    ('usSmallPowerLimit', 'H'), ('usLowCACLeakage', 'H'), ('usHighCACLeakage', 'H'),
    ('usMaximumPowerDeliveryLimit', 'H'), ('usTjMax', 'H'), ('usPowerTuneDataSetID', 'H'), ('usEDCLimit', 'H'),
    ('usSoftwareShutdownTemp', 'H'), ('usClockStretchAmount', 'H'),
]

def read_struct(buf, off, fields):
    fmt = '<' + ''.join(f for _, f in fields)
    vals = struct.unpack_from(fmt, buf, off)
    offs, o = {}, off
    for (n, f) in fields:
        offs[n] = o
        o += struct.calcsize('<' + f)
    return dict(zip([n for n, _ in fields], vals)), offs

def dump(buf):
    h, _ = read_struct(buf, 0, HDR)
    print(f'table size {h["usStructureSize"]} (file {len(buf)}), format rev {h["ucTableFormatRevision"]}.{h["ucTableContentRevision"]}, table rev {h["ucTableRevision"]}')
    print(f'max OD engine clock {h["ulMaxODEngineClock"] / 100:.0f} MHz, max OD memory clock {h["ulMaxODMemoryClock"] / 100:.0f} MHz, '
          f'power control limit (PowerTune slider) {h["usPowerControlLimit"]}%, platform caps 0x{h["ulPlatformCaps"]:08x}')
    pt, _ = read_struct(buf, h['usPowerTuneTableOffset'], POWERTUNE)
    print(f'PowerTune table @ {h["usPowerTuneTableOffset"]} (rev {pt["ucRevId"]}):')
    for k, v in pt.items():
        if k != 'ucRevId':
            print(f'  {k:30s} {v}')
    # sclk / mclk dependency tables: rev, n, records
    so = h['usSclkDependencyTableOffset']
    rev, n = buf[so], buf[so + 1]
    rec = 11 if rev == 0 else 15
    print(f'sclk levels (rev {rev}, {n}):', ', '.join(f'{struct.unpack_from("<I", buf, so + 2 + i * rec + 3)[0] / 100:.0f} MHz' for i in range(n)))
    mo = h['usMclkDependencyTableOffset']
    rev, n = buf[mo], buf[mo + 1]
    print(f'mclk levels (rev {rev}, {n}):', ', '.join(f'{struct.unpack_from("<I", buf, mo + 2 + i * 13 + 9)[0] / 100:.0f} MHz' for i in range(n)))
    ho = h['usHardLimitTableOffset']
    rev, n = buf[ho], buf[ho + 1]
    for i in range(n):
        sc, mc, vddc, vddci, vddgfx = struct.unpack_from('<IIHHH', buf, ho + 2 + i * 14)
        print(f'hard limit {i}: sclk {sc / 100:.0f} MHz, mclk {mc / 100:.0f} MHz, vddc {vddc} mV, vddci {vddci} mV')
    return h, pt

def patch(buf, args):
    buf = bytearray(buf)
    h, _ = read_struct(buf, 0, HDR)
    _, offs = read_struct(buf, h['usPowerTuneTableOffset'], POWERTUNE)
    _, hoffs = read_struct(buf, 0, HDR)
    for a in args:
        k, v = a.split('=')
        v = int(v)
        if k == 'tdp':
            for f in ('usTDP', 'usConfigurableTDP'):
                struct.pack_into('<H', buf, offs[f], v)
        elif k == 'tdc':
            struct.pack_into('<H', buf, offs['usTDC'], v)
        elif k == 'maxpower':
            struct.pack_into('<H', buf, offs['usMaximumPowerDeliveryLimit'], v)
        elif k == 'powercontrol':
            struct.pack_into('<H', buf, hoffs['usPowerControlLimit'], v)
        else:
            raise SystemExit(f'unknown field {k}')
    return bytes(buf)

def get(buf, names):
    h, _ = read_struct(buf, 0, HDR)
    pt, _ = read_struct(buf, h['usPowerTuneTableOffset'], POWERTUNE) if h['ucTableFormatRevision'] == 7 else ({}, None)
    for n in names:
        if n in h:
            print(h[n])
        elif n in pt:
            print(pt[n])
        else:
            raise SystemExit(f'unknown field {n}')

if __name__ == '__main__':
    if sys.argv[1] == 'get':
        get(open(sys.argv[2], 'rb').read(), sys.argv[3:])
    elif sys.argv[1] == 'dump':
        dump(open(sys.argv[2], 'rb').read())
    elif sys.argv[1] == 'patch':
        out = patch(open(sys.argv[2], 'rb').read(), sys.argv[4:])
        open(sys.argv[3], 'wb').write(out)
        dump(out)
