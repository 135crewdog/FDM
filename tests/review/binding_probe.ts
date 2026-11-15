// Reproduce API lifetime, bounds and bulk-memory issues without changing the binding.
import { createSim, describeError } from '../../src/wasm.ts';

const sim = await createSim();
sim.setDebugLevel(0);
sim.loadModel('c172x');
sim.setProperty('review/a', 12);
sim.setProperty('review/b', 34);
for (const path of ['review/bad[', '../../..']) {
  try { console.log('hasProperty',path,'=>',sim.hasProperty(path)); }
  catch(e) { console.log('hasProperty',path,'=>',describeError(e), 'is Error:',e instanceof Error); }
}
try { sim.getProperty('review/bad['); }
catch(e) { console.log('guarded invalid-path message:',describeError(e)); }
sim.setProperty('simulation/sim-time-sec',1234);
console.log('write read-only simulation time returned success; actual:',sim.getProperty('simulation/sim-time-sec'));
const a = sim.handle('review/a'), b = sim.handle('review/b');
for (const h of [-1, 1e10, 0.9, NaN, 2**32+a]) {
  try { console.log('get', h, '=>', sim.get(h)); }
  catch(e) { console.log('get', h, '=>', describeError(e)); }
}
sim.bindInputs([a, b]);
sim.inputs.set([56, 78]);
sim.applyInputs();
sim.bindOutputs([a,b]); sim.readOutputs();
console.log('before growth:', [...sim.outputs]);
const cached = sim.inputs;
const oldBuffer = sim.module.HEAPF64.buffer;
console.log('heap bytes before growth:',oldBuffer.byteLength);
sim.hasProperty('review/'+'x'.repeat(oldBuffer.byteLength*2));
console.log('growth:', sim.module.HEAPF64.buffer !== oldBuffer,
            'old view length:', cached.length, 'new view length:', sim.inputs.length);
sim.inputs.set([90, 91]); sim.applyInputs(); sim.readOutputs();
console.log('after growth:', [...sim.outputs]);
sim.reset();
console.log('after reset inputs/outputs lengths:', sim.inputs.length, sim.outputs.length);
console.log('after reset stale output values:',[...sim.outputs]);
sim.loadModel('f16');
try { sim.inputs.set([888,999]); console.log('reset view write accepted'); }
catch(e) { console.log('reset view write:',describeError(e)); }
try { sim.set(a, 33); } catch(e) { console.log('old handle immediately after reset:',describeError(e)); }
const fresh = sim.handle('ic/h-sl-ft');
console.log('old/fresh handle IDs:',a,fresh);
sim.set(a, 1234);
console.log('old handle now writes fresh property:',sim.getProperty('ic/h-sl-ft'));
sim.dt = 0;
console.log('zero dt accepted:',sim.dt);
sim.setIntegrators({rateRotational: 12345});
console.log('unknown integrator accepted:',sim.getProperty('simulation/integrator/rate/rotational'));
sim.delete();
