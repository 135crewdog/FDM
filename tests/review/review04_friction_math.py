"""Independent frozen-geometry constraint calculation for patch 0001 mode 1.
Checks the mixed translational/rotational leading weights, the RHS and signs.
Does not claim full nonlinear/moving-frame/active-set correctness.
"""
import json
import numpy as np
rng=np.random.default_rng(20261115)
weights={1:[1],2:[.5,.5],3:[1.5,-.5],4:[23/12,-16/12,5/12],5:[55/24,-59/24,37/24,-9/24],
         9:[1901/720,-1387/360,109/30,-637/360,251/720]}
errors=[];old_errors=[];fd_errors=[]
for _ in range(1000):
    mass=rng.uniform(.5,10);q=rng.normal(size=(3,3));inertia=q.T@q+np.eye(3)
    Jinv=np.linalg.inv(inertia);dt=.002
    t,r=map(int,rng.choice(list(weights),size=2));bt,br=weights[t],weights[r]
    slip=rng.normal(size=6);d=rng.normal(size=(5,6))
    rows=[]
    for i in range(3):
        u=rng.normal(size=3);u/=np.linalg.norm(u);arm=rng.normal(size=3)
        rows.append(np.r_[u,np.cross(arm,u)])
    contact=np.array(rows)
    dbar=np.r_[sum(b*d[k,:3] for k,b in enumerate(bt)),sum(b*d[k,3:] for k,b in enumerate(br))]
    mobility=np.zeros((6,6));mobility[:3,:3]=bt[0]/mass*np.eye(3);mobility[3:,3:]=br[0]*Jinv
    A=bt[0]/mass*(contact[:,:3]@contact[:,:3].T)+br[0]*(contact[:,3:]@Jinv@contact[:,3:].T)
    pred=slip+dt*dbar
    lam=np.linalg.solve(A,-contact@pred/dt)
    after=slip+dt*(dbar+mobility@contact.T@lam)
    errors.append(float(np.linalg.norm(contact@after)))
    # Direct finite-difference of the actual discrete velocity update with
    # respect to a constraint force, independently of the A construction above.
    columns=[]
    for k in range(3):
        force=contact[k,:3];torque=contact[k,3:]
        changed=d.copy();changed[0,:3]+=force/mass;changed[0,3:]+=Jinv@torque
        advanced=slip+dt*np.r_[sum(b*changed[j,:3] for j,b in enumerate(bt)),sum(b*changed[j,3:] for j,b in enumerate(br))]
        columns.append(contact@(advanced-pred)/dt)
    fd_errors.append(float(np.max(np.abs(np.column_stack(columns)-A))))
    plain=np.zeros((6,6));plain[:3,:3]=np.eye(3)/mass;plain[3:,3:]=Jinv
    old_rhs=np.r_[pred[:3]/bt[0],pred[3:]/br[0]]
    old_lam=np.linalg.solve(contact@plain@contact.T,-contact@old_rhs/dt)
    old_errors.append(float(np.linalg.norm(contact@(pred+dt*mobility@contact.T@old_lam))))
assert max(errors)<1e-10
assert max(fd_errors)<1e-10
print(json.dumps(dict(samples=len(errors),max_mode1_slip_residual=max(errors),
    max_matrix_finite_difference_error=max(fd_errors),max_2010_mixed_weight_slip_residual=max(old_errors))))
