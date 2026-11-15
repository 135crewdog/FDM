// Minimal embind binding for JSBSim (FDM project).
//
// Design:
// - Every call that can reach JSBSim code catches C++ exceptions here and stores the message
//   (lastError()). It then returns a status code; the TypeScript wrapper (src/jsbsim.ts) turns that
//   into a JavaScript Error carrying the C++ message. No exception ever crosses into JavaScript.
// - Fast property access: look a property up once (handle()), then get/set by integer handle,
//   or bind lists of handles as inputs/outputs and exchange one Float64Array per step (bulk).
// - Physics is untouched: this file only calls FGFDMExec's public API.

#include <emscripten/bind.h>
#include <emscripten/val.h>

#include <limits>
#include <memory>
#include <string>
#include <vector>

#include "FGFDMExec.h"
#include "FGJSBBase.h"
#include "input_output/FGPropertyManager.h"
#include "simgear/misc/sg_path.hxx"

using namespace emscripten;
using JSBSim::FGFDMExec;

namespace {

class Sim {
 public:
  Sim() = default;

  // Status codes returned to JS: >= 0 success (meaning depends on call), -1 = C++ exception
  // (message in lastError()).
  static constexpr int ERR = -1;

  int init(const std::string& root) {
    return guard([&] {
      fdm_ = std::make_unique<FGFDMExec>(nullptr, nullptr);
      // Same set-up as the Python package's FGFDMExec(root_dir).
      fdm_->SetRootDir(SGPath(root));
      fdm_->SetOutputPath(SGPath("."));
      fdm_->SetEnginePath(SGPath("engine"));
      fdm_->SetAircraftPath(SGPath("aircraft"));
      fdm_->SetSystemsPath(SGPath("systems"));
      handles_.clear();
      in_.clear(); out_.clear();
      inBuf_.clear(); outBuf_.clear();
      return 1;
    });
  }

  // 1 = loaded, 0 = JSBSim returned false (see console log), -1 = exception.
  int loadModel(const std::string& model, bool addModelToPath) {
    return guard([&] { return fdm()->LoadModel(model, addModelToPath) ? 1 : 0; });
  }
  int loadScript(const std::string& script, double dt, const std::string& initfile) {
    return guard([&] { return fdm()->LoadScript(SGPath(script), dt, SGPath(initfile)) ? 1 : 0; });
  }
  int runIC() {
    return guard([&] { return fdm()->RunIC() ? 1 : 0; });
  }
  // 1 = continue, 0 = script finished (Run returned false), -1 = exception.
  int run() {
    return guard([&] { return fdm()->Run() ? 1 : 0; });
  }
  // Run up to n steps. Returns steps completed (stops early when Run() returns false), or -1.
  int runSteps(int n) {
    return guard([&] {
      int i = 0;
      while (i < n) {
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
  // Same semantics as FGFDMExec::SetPropertyValue: creates the property if it does not exist.
  int setProperty(const std::string& name, double value) {
    return guard([&] { fdm()->SetPropertyValue(name, value); return 1; });
  }
  bool hasProperty(const std::string& name) {
    return fdm_ && fdm_->GetPropertyManager()->HasNode(name);
  }

  // --- cached handles ---
  // Returns a handle (>= 0), or -1 (missing property, message in lastError()).
  int handle(const std::string& name, bool create) {
    return guard([&] {
      SGPropertyNode* node = fdm()->GetPropertyManager()->GetNode(name, create);
      if (!node) throw JSBSim::BaseException("No property named " + name);
      handles_.push_back(node);
      return static_cast<int>(handles_.size() - 1);
    });
  }
  // An invalid handle reads NaN / fails with -1 (bounds checked: one compare per call).
  double get(int h) {
    if (static_cast<unsigned>(h) >= handles_.size()) return std::numeric_limits<double>::quiet_NaN();
    return handles_[h]->getDoubleValue();
  }
  int set(int h, double v) {
    if (static_cast<unsigned>(h) >= handles_.size()) { err_ = "invalid handle " + std::to_string(h); return ERR; }
    return guard([&] { handles_[h]->setDoubleValue(v); return 1; });
  }

  // --- bulk exchange: one Float64Array in, one out ---
  int bindInputs(val list) { return bindList(list, in_, inBuf_); }
  int bindOutputs(val list) { return bindList(list, out_, outBuf_); }
  uintptr_t inputPtr() { return reinterpret_cast<uintptr_t>(inBuf_.data()); }
  uintptr_t outputPtr() { return reinterpret_cast<uintptr_t>(outBuf_.data()); }
  int applyInputs() {
    return guard([&] {
      for (size_t i = 0; i < in_.size(); ++i) handles_[in_[i]]->setDoubleValue(inBuf_[i]);
      return 1;
    });
  }
  void readOutputs() {
    for (size_t i = 0; i < out_.size(); ++i) outBuf_[i] = handles_[out_[i]]->getDoubleValue();
  }
  // Apply inputs, run up to n steps, read outputs. Returns steps completed, or -1.
  int stepBulk(int n) {
    return guard([&] {
      for (size_t i = 0; i < in_.size(); ++i) handles_[in_[i]]->setDoubleValue(inBuf_[i]);
      int i = 0;
      bool more = true;
      while (i < n && more) { ++i; more = fdm()->Run(); }
      for (size_t k = 0; k < out_.size(); ++k) outBuf_[k] = handles_[out_[k]]->getDoubleValue();
      return more ? i : -(i + 2);  // -(i+2) => script ended after i steps (distinct from -1)
    });
  }

  // --- misc ---
  double getDt() const { return fdm_ ? fdm_->GetDeltaT() : 0.0; }
  void setDt(double dt) { if (fdm_) fdm_->Setdt(dt); }
  double simTime() const { return fdm_ ? fdm_->GetSimTime() : 0.0; }
  void setDebugLevel(int lvl) {
    if (fdm_) fdm_->SetDebugLevel(lvl); else JSBSim::FGJSBBase::debug_lvl = lvl;
  }
  int lastStatus() const { return lastStatus_; }
  std::string lastError() const { return err_; }
  static std::string version() { return JSBSim::FGJSBBase::GetVersion(); }

 private:
  FGFDMExec* fdm() {
    if (!fdm_) throw JSBSim::BaseException("Sim not initialised: call init(root) first");
    return fdm_.get();
  }

  template <class F>
  int guard(F&& f) {
    err_.clear();
    try {
      return f();
    } catch (const std::exception& e) {
      err_ = e.what();
    } catch (...) {
      err_ = "unknown C++ exception";
    }
    if (err_.empty()) err_ = "C++ exception with empty message";
    return ERR;
  }

  int bindList(val list, std::vector<int>& idx, std::vector<double>& buf) {
    std::vector<int> v = vecFromJSArray<int>(list);
    for (int h : v)
      if (h < 0 || h >= static_cast<int>(handles_.size())) {
        err_ = "invalid handle " + std::to_string(h);
        return ERR;
      }
    idx = std::move(v);
    buf.assign(idx.size(), 0.0);
    return static_cast<int>(idx.size());
  }

  std::unique_ptr<FGFDMExec> fdm_;
  std::vector<SGPropertyNode_ptr> handles_;
  std::vector<int> in_, out_;
  std::vector<double> inBuf_, outBuf_;
  std::string err_;
  int lastStatus_ = 1;
};

}  // namespace

EMSCRIPTEN_BINDINGS(fdm_jsbsim) {
  class_<Sim>("Sim")
      .constructor<>()
      .function("init", &Sim::init)
      .function("loadModel", &Sim::loadModel)
      .function("loadScript", &Sim::loadScript)
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
