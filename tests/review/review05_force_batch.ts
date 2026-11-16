// Recompute a game's state-dependent moment once per bulk call, at different batch sizes.
import {createSim} from '../../src/wasm.ts';
const s=await createSim({profile:'fdm'});
const xml=`<fdm_config name="probe" version="2.0" release="BETA"><planet><rotation_rate>0</rotation_rate></planet><metrics/><mass_balance><ixx unit="SLUG*FT2">1</ixx><iyy unit="SLUG*FT2">1</iyy><izz unit="SLUG*FT2">1</izz><emptywt unit="LBS">32.174049</emptywt></mass_balance><ground_reactions/><external_reactions><moment name="roll" frame="BODY"><direction><x>1</x><y>0</y><z>0</z></direction></moment></external_reactions><aerodynamics/></fdm_config>`;
s.writeFile('aircraft/review05_probe/review05_probe.xml',xml);
for(const batch of [1,8,16,20]){
 s.reset();s.loadModel('review05_probe');s.setProperty('ic/h-sl-ft',100000);s.setProperty('ic/p-rad_sec',.5);s.runIC();
 s.bindInputs(['external_reactions/roll/magnitude-lbsft']);s.bindOutputs(['velocities/p-rad_sec']);s.readOutputs();
 let peak=.5;for(let k=0;k<1200/batch;k++){s.inputs[0]=-180*s.outputs[0]!;s.step(batch);peak=Math.max(peak,Math.abs(s.outputs[0]!));}
 console.log(JSON.stringify({hz:1200,damping:180,batch,peak,final:s.outputs[0],exact:.5*Math.exp(-180)}));
}
s.delete();
