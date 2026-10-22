"""Generate project UI line icons with Pillow; no game assets."""
from pathlib import Path
from PIL import Image,ImageDraw
scale=16
atlas=Image.new('RGBA',(384*4,128*4))
def icon(col,row,lines,color):
 im=Image.new('RGBA',(24*scale,24*scale));d=ImageDraw.Draw(im)
 for points in lines:
  p=[(x*scale,y*scale) for x,y in points];w=round(1.9*scale)
  d.line(p,fill=color,width=w,joint='curve')
  for x,y in [p[0],p[-1]]:d.ellipse((x-w/2,y-w/2,x+w/2,y+w/2),fill=color)
 atlas.paste(im.resize((256,256),Image.Resampling.LANCZOS),(col*256,row*256))
display=[[(3,7),(9,4),(15,7),(21,4),(21,17),(15,20),(9,17),(3,20),(3,7)],[(9,4),(9,17)],[(15,7),(15,20)]]
ai=[[(7,8),(17,8),(17,18),(7,18),(7,8)],[(12,4),(12,8)],[(9,13),(9.01,13)],[(15,13),(15.01,13)],[(4,12),(7,12)],[(17,12),(20,12)]]
wrench=[[(14.5,5.5),(12.3,5.1),(10.3,6),(9.1,8),(9.5,10.5),(4,16),(8,20),(13.5,14.5),(16,14.9),(18,13.7),(18.9,11.7),(18.5,9.5),(16,12),(13,11),(12,8),(14.5,5.5)]]
for row,color in [(0,'#9AA4B8'),(1,'#E8ECF4')]:
 for col,lines in enumerate([display,ai,wrench]):icon(col,row,lines,color)
icon(3,0,[[(12,3),(22,21),(2,21),(12,3)],[(12,10),(12,15)],[(12,18),(12,18.5)]],'#FFB23E')
icon(4,0,[[(2,9),(13,9),(15,7),(21,7),(21,10),(19,10),(19,12),(15,12),(14,14),(9.5,14),(8.3,18),(5,18),(6.1,14),(3,14),(2,9)],[(7,9),(7,7),(11,7),(11,9)],[(14,10),(17,10)],[(21,8.5),(22.5,8.5)]],'#FFB23E')
# Open padlock and sparkle from the owner's exact Floyd reference path.
from math import pi,sin,cos,atan2
sweep=atan2(-1.7,3.6)+pi
shackle=[(8,11)]+[(12+4*cos(pi+sweep*i/32),7+4*sin(pi+sweep*i/32)) for i in range(33)]
icon(5,0,[[(5,11),(17,11),(17,21),(5,21),(5,11)],shackle,[(11,15),(11,17)],[(19,3),(19,6)],[(17.5,4.5),(20.5,4.5)]],'#6FD3EE')
asset=Path(__file__).with_name('mods-icons.tga')
atlas.resize((384,128),Image.Resampling.LANCZOS).save(asset)
