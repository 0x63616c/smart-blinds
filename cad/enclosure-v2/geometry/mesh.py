"""Float32 STL evidence without repairing, smoothing or rounding coordinates."""
from pathlib import Path
import re,numpy as np

def stl(path):
 b=Path(path).read_bytes()
 if len(b)>=84 and 84+50*int.from_bytes(b[80:84],'little')==len(b):
  dt=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('a','<u2')]);return np.frombuffer(b,dt,offset=84)['v'].astype(float)
 return np.array([[float(x)for x in q]for q in re.findall(rb'vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)',b)]).reshape(-1,3,3)

def canonical_triangles(tris):
 t=np.asarray(tris,dtype=np.float32).copy()
 # Compare geometric triangles, independent of STL face/vertex enumeration.
 ix=np.lexsort(t.transpose(2,0,1)[::-1],axis=1)
 t=np.take_along_axis(t,ix[:,:,None],axis=1).reshape(-1,9)
 return t[np.lexsort(t.T[::-1])]

def topology(t):
 v,ix=np.unique(t.reshape(-1,3),axis=0,return_inverse=True);f=ix.reshape(-1,3)
 edges=np.sort(f[:,[[0,1],[1,2],[2,0]]].reshape(-1,2),axis=1);ed,c=np.unique(edges,axis=0,return_counts=True)
 roots=list(range(len(v)))
 def find(a):
  while roots[a]!=a:roots[a]=roots[roots[a]];a=roots[a]
  return a
 for a,b in ed:
  x,y=find(int(a)),find(int(b));roots[x]=y
 return {'triangles':len(t),'vertices':len(v),'closed_edges':bool(np.all(c==2)),'connected_components':len({find(i)for i in range(len(v))}),'bounds':[t.min((0,1)).tolist(),t.max((0,1)).tolist()],'volume_mm3':abs(float(np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])).sum()))/6}

from geometry.operations import overlap,inside_mesh,mesh_box,box_faces
