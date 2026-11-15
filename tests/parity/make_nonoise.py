"""Copy jsbsim-data to out/nonoise with the c172x autopilot's Gaussian sensor noise removed.
JSBSim draws noise from std::default_random_engine + std::normal_distribution, whose algorithms differ
between libstdc++ (native Linux) and libc++ (Emscripten), so noisy models cannot match step for step."""
import os, re, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(HERE, "..", "..", "jsbsim-data"); dst = os.path.join(HERE, "..", "..", "out", "nonoise")
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(src, dst, ignore=shutil.ignore_patterns("check_cases"))
p = os.path.join(dst, "aircraft", "c172x", "c172ap.xml")
x = open(p).read(); y = re.sub(r"\s*<noise[^>]*>[^<]*</noise>", "", x)
assert x != y
open(p, "w").write(y)
print("wrote", os.path.abspath(dst), "(c172ap.xml: <noise> removed)")
