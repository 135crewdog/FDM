// Minimal embind binding for JSBSim (FDM project).
//
// Design:
// - EVERY public call that can reach JSBSim code catches EVERY C++ exception here (std::exception, the
//   std::string and const char* that JSBSim's property code throws, and anything else) and stores the
//   message (lastError()). It then returns a status code; the TypeScript wrapper (src/jsbsim.ts) turns
//   that into a JSBSimError carrying the C++ message. No exception ever crosses into JavaScript.
// - Nothing fails silently: a write to a read-only property, an invalid handle, an unknown integrator
//   id, a non-positive or non-finite dt and an invalid step count are all errors.
// - Fast property access: look a property up once (handle()), then get/set by handle, or bind lists of
//   handles as inputs/outputs and exchange one Float64Array per step (bulk).
// - Handle lifetime: a handle belongs to the FGFDMExec instance that was current when it was made.
//   init() (the wrapper's reset()) starts a new "generation": every earlier handle becomes invalid and
//   is rejected (never aliased to a new property), and the bulk input/output lists become empty.
//   Handles are numbers: generation * 2^20 + index. They are passed as doubles so that NaN, fractions
//   and out-of-range values can be rejected here instead of being wrapped by an integer conversion.
// - Socket input (<input port=...> in aircraft files, e.g. the 737 and c172x) is disabled: a phone
//   game has no use for it, and in Node it needs the npm package "ws". It never affects the physics
//   unless something connects to the port.
// - Physics is untouched: this file only calls FGFDMExec's public API.

#include <emscripten/bind.h>
#include <emscripten/val.h>

#include <cmath>
#include <limits>
#include <memory>
#include <string>
#include <vector>

#include "FGFDMExec.h"
#include "FGJSBBase.h"
#include "initialization/FGInitialCondition.h"
#include "input_output/FGPropertyManager.h"
#include "models/FGInput.h"
#include "simgear/misc/sg_path.hxx"

using namespace emscripten;
using JSBSim::FGFDMExec;

namespace {

std::string num(double v) {
  if (std::isnan(v)) return "NaN";
  if (std::isinf(v)) return v > 0 ? "Infinity" : "-Infinity";
  if (v == std::floor(v) && std::fabs(v) < 1e15) return std::to_string(static_cast<long long>(v));
  return std::to_string(v);
}

class Sim {
 public:
  Sim() = default;

  // Status codes returned to JS: >= 0 success (meaning depends on call), -1 = error (message in
  // lastError()).
  static constexpr int ERR = -1;
  static constexpr double STRIDE = 1048576.0;  // 2^20 handles per generation

  int init(const std::string& root) {
    return guard([&] {
      // A new generation: old handles and bulk bindings die with the old FGFDMExec.
      if (everInit_) base_ += STRIDE;
      everInit_ = true;
      std::vector<Handle>().swap(handles_);
      std::vector<int>().swap(in_); std::vector<int>().swap(out_);
      std::vector<double>().swap(inBuf_); std::vector<double>().swap(outBuf_);
      for (auto& n : integ_) n = nullptr;
      fdm_.reset();
      fdm_ = std::make_unique<FGFDMExec>(nullptr, nullptr);
      // Same set-up as the Python package's FGFDMExec(root_dir).
      fdm_->SetRootDir(SGPath(root));
      fdm_->SetOutputPath(SGPath("."));
      fdm_->SetEnginePath(SGPath("engine"));
      fdm_->SetAircraftPath(SGPath("aircraft"));
      fdm_->SetSystemsPath(SGPath("systems"));
      // No socket input in this runtime (see the header comment). Input elements loaded later
      // inherit the disabled state, so no socket is ever created.
      fdm_->GetInput()->Disable();
      static const char* names[4] = {"simulation/integrator/rate/rotational", "simulation/integrator/rate/translational",
                                     "simulation/integrator/position/rotational", "simulation/integrator/position/translational"};
      for (int k = 0; k < 4; ++k) integ_[k] = fdm_->GetPropertyManager()->GetNode(names[k], false);
      return 1;
    });
  }

  // 1 = loaded, 0 = JSBSim returned false (see console log), -1 = exception.
  int loadModel(const std::string& model, bool addModelToPath) {
    return guard([&] { return fdm()->LoadModel(model, addModelToPath) ? 1 : 0; });
  }
  // dt = 0 means "the script's own dt".
  int loadScript(const std::string& script, double dt, const std::string& initfile) {
    return guard([&] {
      if (!(dt >= 0.0) || !std::isfinite(dt)) throw JSBSim::BaseException("invalid dt " + num(dt) + " (must be finite and positive, or 0 for the script's own dt)");
      return fdm()->LoadScript(SGPath(script), dt, SGPath(initfile)) ? 1 : 0;
    });
  }
  // Load an initial-conditions file, like the Python module's load_ic(): with useAircraftPath the name
  // is looked up in the loaded aircraft's folder ("reset00" -> aircraft/<model>/reset00.xml).
  int loadIC(const std::string& name, bool useAircraftPath) {
    return guard([&] { return fdm()->GetIC()->Load(SGPath(name), useAircraftPath) ? 1 : 0; });
  }
  int runIC() {
    return guard([&] { return fdm()->RunIC() ? 1 : 0; });
  }
  // 1 = continue, 0 = script finished (Run returned false), -1 = exception.
  int run() {
    return guard([&] { return fdm()->Run() ? 1 : 0; });
  }
  // Run up to n steps. Returns steps completed (stops early when Run() returns false), or -1.
  int runSteps(double n) {
    return guard([&] {
      int count = stepCount(n), i = 0;
      while (i < count) {
        ++i;
        if (!fdm()->Run()) break;
      }
      return i;
    });
  }

  // --- properties by name (convenient, slower: string conversion + tree lookup per call) ---
  // Same semantics as FGFDMExec::GetPropertyValue: a missing property reads 0.
  double getProperty(const std::string& name) {
    double v = 0.0;
    lastStatus_ = guard([&] { v = fdm()->GetPropertyValue(name); return 1; });
    return v;
  }
  // Like FGFDMExec::SetPropertyValue it creates the property if it does not exist, but a write
  // that JSBSim refuses (read-only property) is an error.
  int setProperty(const std::string& name, double value) {
    return guard([&] {
      SGPropertyNode* node = fdm()->GetPropertyManager()->GetNode(name, true);
      if (!node) throw JSBSim::BaseException("cannot create property " + name);
      write(node, kindOf(node), value);
      return 1;
    });
  }
  // 1 = exists, 0 = does not, -1 = error (e.g. malformed path).
  int hasProperty(const std::string& name) {
    return guard([&] { return fdm()->GetPropertyManager()->HasNode(name) ? 1 : 0; });
  }

  // --- cached handles ---
  // Returns a handle (>= 0), or -1 (missing property, message in lastError()).
  double handle(const std::string& name, bool create) {
    return guard([&] {
      SGPropertyNode* node = fdm()->GetPropertyManager()->GetNode(name, create);
      if (!node) throw JSBSim::BaseException("No property named " + name);
      if (handles_.size() >= static_cast<size_t>(STRIDE)) throw JSBSim::BaseException("too many handles");
      handles_.push_back({node, kindOf(node)});
      return static_cast<int>(handles_.size() - 1);
    }, base_);
  }
  // An invalid handle or a failing getter reads NaN with lastStatus() = -1.
  double get(double h) {
    double v = std::numeric_limits<double>::quiet_NaN();
    lastStatus_ = guard([&] { v = at(h).node->getDoubleValue(); return 1; });
    return v;
  }
  int set(double h, double v) {
    return guard([&] { Handle& x = at(h); write(x.node, x.kind, v); return 1; });
  }

  // --- bulk exchange: one Float64Array in, one out ---
  // A failed bind leaves the previous binding unchanged.
  int bindInputs(val list) { return bindList(list, in_, inBuf_, true); }
  int bindOutputs(val list) { return bindList(list, out_, outBuf_, false); }
  uintptr_t inputPtr() { return reinterpret_cast<uintptr_t>(inBuf_.data()); }
  uintptr_t outputPtr() { return reinterpret_cast<uintptr_t>(outBuf_.data()); }
  int inputCount() const { return static_cast<int>(in_.size()); }
  int outputCount() const { return static_cast<int>(out_.size()); }
  int applyInputs() {
    return guard([&] { applyIn(); return 1; });
  }
  int readOutputs() {
    return guard([&] { readOut(); return 1; });
  }
  // Apply inputs, run up to n steps, read outputs. Returns steps completed, or -1.
  int stepBulk(double n) {
    return guard([&] {
      int count = stepCount(n);
      applyIn();
      int i = 0;
      bool more = true;
      while (i < count && more) { ++i; more = fdm()->Run(); }
      readOut();
      return more ? i : -(i + 2);  // -(i+2) => script ended after i steps (distinct from -1)
    });
  }

  // --- misc ---
  double getDt() const { return fdm_ ? fdm_->GetDeltaT() : 0.0; }
  // Set dt BEFORE loading a model: flight-control filters cache dt when they are loaded.
  int setDt(double dt) {
    return guard([&] {
      if (!(dt > 0.0) || !std::isfinite(dt)) throw JSBSim::BaseException("invalid dt " + num(dt) + " (must be finite and positive)");
      fdm()->Setdt(dt);
      return 1;
    });
  }
  double simTime() const { return fdm_ ? fdm_->GetSimTime() : 0.0; }
  void setDebugLevel(int lvl) {
    if (fdm_) fdm_->SetDebugLevel(lvl); else JSBSim::FGJSBBase::debug_lvl = lvl;
  }
  int lastStatus() const { return lastStatus_; }
  std::string lastError() const { return err_; }
  static std::string version() { return JSBSim::FGJSBBase::GetVersion(); }

 private:
  // kind: 0 ordinary property, 1 integrator selector (rates, translational position), 2 integrator
  // selector for rotational position (attitude), which also accepts the quaternion methods.
  struct Handle { SGPropertyNode_ptr node; int kind; };

  FGFDMExec* fdm() {
    if (!fdm_) throw JSBSim::BaseException("Sim not initialised: call init(root) first");
    return fdm_.get();
  }

  Handle& at(double h) {
    double i = h - base_;
    if (!(i >= 0.0 && i < static_cast<double>(handles_.size())) || i != std::floor(i))
      throw JSBSim::BaseException("invalid handle " + num(h) + " (a handle is the integer returned by handle(); reset() invalidates all earlier handles)");
    return handles_[static_cast<size_t>(i)];
  }

  int kindOf(const SGPropertyNode* node) const {
    for (int k = 0; k < 4; ++k) if (integ_[k] && node == integ_[k].ptr()) return k == 2 ? 2 : 1;
    return 0;
  }

  // The only place that writes a property.
  void write(SGPropertyNode* node, int kind, double v) {
    if (kind != 0) {
      // JSBSim's integration switch silently does nothing for an unknown id (freezing the state).
      bool ok = v == std::floor(v) && v >= 0.0 && v <= 9.0 && (kind == 2 || !(v >= 6.0 && v <= 8.0));
      if (!ok)
        throw JSBSim::BaseException("invalid integrator id " + num(v) + " for " + JSBSim::GetFullyQualifiedName(node) +
                                    " (valid: 0 none, 1 Euler, 2 trapezoidal, 3 AB2, 4 AB3, 5 AB4, 9 AB5" +
                                    (kind == 2 ? ", 6 Buss 1, 7 Buss 2, 8 local linearization)" : "; 6-8 are for position/rotational only)"));
    }
    if (!node->setDoubleValue(v))
      throw JSBSim::BaseException("cannot write " + JSBSim::GetFullyQualifiedName(node) + ": the property is read-only");
  }

  static int stepCount(double n) {
    if (!(n >= 0.0 && n <= 2147483647.0) || n != std::floor(n))
      throw JSBSim::BaseException("invalid step count " + num(n) + " (must be a non-negative integer)");
    return static_cast<int>(n);
  }

  void applyIn() {
    for (size_t i = 0; i < in_.size(); ++i) { Handle& x = handles_[in_[i]]; write(x.node, x.kind, inBuf_[i]); }
  }
  void readOut() {
    for (size_t k = 0; k < out_.size(); ++k) outBuf_[k] = handles_[out_[k]].node->getDoubleValue();
  }

  template <class F, class R = int>
  R guard(F&& f, R offset = R()) {
    err_.clear();
    try {
      return static_cast<R>(f()) + offset;
    } catch (const std::exception& e) {
      err_ = e.what();
    } catch (const std::string& s) {   // JSBSim's property path parser throws std::string
      err_ = s;
    } catch (const char* s) {
      err_ = s ? s : "";
    } catch (...) {
      err_ = "unknown C++ exception";
    }
    if (err_.empty()) err_ = "C++ exception with empty message";
    return static_cast<R>(ERR);
  }

  int bindList(val list, std::vector<int>& idx, std::vector<double>& buf, bool input) {
    return guard([&] {
      std::vector<double> raw = vecFromJSArray<double>(list);
      std::vector<int> v;
      v.reserve(raw.size());
      for (double h : raw) {
        Handle& x = at(h);
        if (input && !x.node->getAttribute(SGPropertyNode::WRITE))
          throw JSBSim::BaseException("cannot bind " + JSBSim::GetFullyQualifiedName(x.node) + " as an input: the property is read-only");
        v.push_back(static_cast<int>(h - base_));
      }
      idx = std::move(v);
      buf.assign(idx.size(), 0.0);
      return static_cast<int>(idx.size());
    });
  }

  std::unique_ptr<FGFDMExec> fdm_;
  std::vector<Handle> handles_;
  SGPropertyNode_ptr integ_[4];
  std::vector<int> in_, out_;
  std::vector<double> inBuf_, outBuf_;
  std::string err_;
  double base_ = 0.0;
  bool everInit_ = false;
  int lastStatus_ = 1;
};

}  // namespace

EMSCRIPTEN_BINDINGS(fdm_jsbsim) {
  class_<Sim>("Sim")
      .constructor<>()
      .function("init", &Sim::init)
      .function("loadModel", &Sim::loadModel)
      .function("loadScript", &Sim::loadScript)
      .function("loadIC", &Sim::loadIC)
      .function("runIC", &Sim::runIC)
      .function("run", &Sim::run)
      .function("runSteps", &Sim::runSteps)
      .function("getProperty", &Sim::getProperty)
      .function("setProperty", &Sim::setProperty)
      .function("hasProperty", &Sim::hasProperty)
      .function("handle", &Sim::handle)
      .function("get", &Sim::get)
      .function("set", &Sim::set)
      .function("bindInputs", &Sim::bindInputs)
      .function("bindOutputs", &Sim::bindOutputs)
      .function("inputPtr", &Sim::inputPtr)
      .function("outputPtr", &Sim::outputPtr)
      .function("inputCount", &Sim::inputCount)
      .function("outputCount", &Sim::outputCount)
      .function("applyInputs", &Sim::applyInputs)
      .function("readOutputs", &Sim::readOutputs)
      .function("stepBulk", &Sim::stepBulk)
      .function("getDt", &Sim::getDt)
      .function("setDt", &Sim::setDt)
      .function("simTime", &Sim::simTime)
      .function("setDebugLevel", &Sim::setDebugLevel)
      .function("lastStatus", &Sim::lastStatus)
      .function("lastError", &Sim::lastError)
      .class_function("version", &Sim::version);
}
