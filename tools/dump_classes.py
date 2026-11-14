"""Dump smali-like bytecode of app classes matching prefixes. Usage: dump_classes.py base.apk outdir prefix..."""
import sys, os
from androguard.misc import AnalyzeAPK
from loguru import logger
logger.remove()

apk_path, out = sys.argv[1], sys.argv[2]
prefixes = sys.argv[3:]
a, ds, dx = AnalyzeAPK(apk_path)
os.makedirs(out, exist_ok=True)
for d in ds:
    for c in d.get_classes():
        name = c.get_name()
        if not any(name.startswith('L' + p) for p in prefixes):
            continue
        fn = os.path.join(out, name[1:-1].replace('/', '.').replace('$', '_') + '.smali.txt')
        with open(fn, 'w', encoding='utf-8') as f:
            f.write(f'class {name} extends {c.get_superclassname()}\n')
            for fld in c.get_fields():
                f.write(f'  field {fld.get_name()} {fld.get_descriptor()} = {fld.get_init_value().get_value() if fld.get_init_value() else ""}\n')
            for m in c.get_methods():
                f.write(f'\n.method {m.get_name()}{m.get_descriptor()}\n')
                code = m.get_code()
                if not code:
                    continue
                for ins in code.get_bc().get_instructions():
                    f.write(f'    {ins.get_name()} {ins.get_output()}\n')
        print(fn)
