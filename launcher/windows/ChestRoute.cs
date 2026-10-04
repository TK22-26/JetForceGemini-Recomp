using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace JfgLauncher {
    internal sealed class ChestApproach {
        internal HeightPoint Target, Staging;
    }
    internal static class ChestPlanner {
        internal static ChestApproach Approach(MapSnapshot map,MapInteraction chest) {
            if(chest==null||chest.action!="open_chest"||chest.activation==null||!chest.activation.known)
                throw new InvalidDataException("Chest activation geometry is unavailable. Press A once during gameplay, then refresh.");
            var a=chest.activation;var centre=new HeightPoint(a.point);var actor=new HeightPoint(chest.position);
            float dx=centre.X-actor.X,dz=centre.Z-actor.Z,len=(float)Math.Sqrt(dx*dx+dz*dz);
            if(len<1||a.radius<=6)throw new InvalidDataException("No supported chest approach direction.");
            dx/=len;dz/=len;float y;
            // Stand inside the activation circle, on its side away from the
            // chest. Do not plan toward the solid centre of the chest model.
            var target=new HeightPoint(centre.X+dx*(a.radius-5),centre.Y,centre.Z+dz*(a.radius-5));
            if(!BoxJumpPlanner.Floor(map.Mesh,target.X,target.Z,centre.Y,8,out y))
                throw new InvalidDataException("Chest opening point has no supporting floor.");
            target.Y=y+BoxJumpPlanner.Offset(map);
            var stage=new HeightPoint(target.X+dx*60,target.Y,target.Z+dz*60);
            float stageY;
            if(!BoxJumpPlanner.Floor(map.Mesh,stage.X,stage.Z,target.Y,64,out stageY))
                throw new InvalidDataException("Chest staging point has no supporting floor.");
            stage.Y=stageY+BoxJumpPlanner.Offset(map);
            var floors=new MapLayers(map.Mesh).Floors;
            if(!NavigationRoute.ClearWalk(map,floors,stage,target,0))
                throw new InvalidDataException("Chest opening point lacks body clearance.");
            return new ChestApproach{Target=target,Staging=stage};
        }
    }
}
