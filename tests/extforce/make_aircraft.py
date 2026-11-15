"""Make copies of c172p with N runtime-controllable external forces (into git-ignored jsbsim-data/).
Also writes a matching script. usage: python tests/extforce/make_aircraft.py 0 1 20   (0 = no force at all: the benchmark baseline)"""
import os, re, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "jsbsim-data")

def make(n):
    name = f"c172p_ext{n}"
    src = open(os.path.join(ROOT, "aircraft/c172p/c172p.xml")).read()
    src = re.sub(r"<output name=.*?</output>", "", src, flags=re.S)  # drop file output
    forces = "".join(f"""
    <force name="f{i}" frame="BODY">
      <location unit="IN"> <x> 43.2 </x> <y> 0 </y> <z> 59.4 </z> </location>
      <direction> <x> 0 </x> <y> 0 </y> <z> -1 </z> </direction>
    </force>""" for i in range(n))
    src = src.replace("</fdm_config>", f"  <external_reactions>{forces}\n  </external_reactions>\n</fdm_config>")
    d = os.path.join(ROOT, "aircraft", name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, name + ".xml"), "w").write(src)
    open(os.path.join(d, "reset01.xml"), "w").write(open(os.path.join(ROOT, "aircraft/c172p/reset01.xml")).read())
    open(os.path.join(ROOT, "scripts", f"ext_{name}.xml"), "w").write(f"""<?xml version="1.0"?>
<runscript name="external force test {name}">
  <use aircraft="{name}" initialize="reset01"/>
  <run start="0.0" end="1000" dt="0.008333333333333333"/>
</runscript>
""")

for a in sys.argv[1:] or ["0", "1", "20"]:
    make(int(a))
