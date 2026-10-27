using System;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;
// Renders the finalized clip-on bundles with the game's own shaders into clipons/previews/<key>_<view>.png.
// Run: -executeMethod ClipOnRenderCheck.Run
public static class ClipOnRenderCheck {
 const string Root="D:/games/SPT-4.1.6";
 const string Bundles=Root+"/.codex-work/EFTClipOnSight/clipons/package/bundles/ustachae_clipons";
 const string Output=Root+"/.codex-work/EFTClipOnSight/clipons/previews";
 public static void Run(){
  Directory.CreateDirectory(Output);
  AssetBundle.LoadFromFile(Root+"/EscapeFromTarkov_Data/StreamingAssets/Windows/shaders");
  AssetBundle.LoadFromFile(Root+"/EscapeFromTarkov_Data/StreamingAssets/Windows/cubemaps");
  RenderSettings.ambientMode=AmbientMode.Trilight;
  RenderSettings.ambientSkyColor=new Color(.45f,.48f,.55f);RenderSettings.ambientEquatorColor=new Color(.28f,.28f,.29f);RenderSettings.ambientGroundColor=new Color(.12f,.12f,.13f);
  var l=new GameObject("key").AddComponent<Light>();l.type=LightType.Directional;l.intensity=1.3f;l.transform.rotation=Quaternion.Euler(35,-35,0);
  var fill=new GameObject("fill").AddComponent<Light>();fill.type=LightType.Directional;fill.intensity=.5f;fill.transform.rotation=Quaternion.Euler(20,140,0);
  var cam=new GameObject("camera").AddComponent<Camera>();cam.clearFlags=CameraClearFlags.SolidColor;cam.backgroundColor=new Color(.55f,.58f,.62f);cam.fieldOfView=30;cam.nearClipPlane=.001f;cam.farClipPlane=100;cam.aspect=1.6f;
  foreach(var path in Directory.GetFiles(Bundles,"*.bundle")){
   string key=Path.GetFileNameWithoutExtension(path);
   var bundle=AssetBundle.LoadFromFile(path);if(bundle==null)throw new Exception("Bundle failed to load: "+path);
   var go=UnityEngine.Object.Instantiate(bundle.LoadAsset<GameObject>(bundle.GetAllAssetNames().Single(x=>x.EndsWith(".prefab"))));
   foreach(var r in go.GetComponentsInChildren<Renderer>())foreach(var m in r.sharedMaterials)if(m==null||!m.shader.isSupported)throw new Exception("Unsupported material "+(m==null?"null":m.name+" "+m.shader.name));
   var b=go.GetComponentsInChildren<Renderer>().First(r=>r.name.EndsWith("LOD0")).bounds;
   var axis=go.transform.Find("clipon_axis").localPosition.y;
   var views=new[]{("iso",new Vector3(1.2f,.7f,-1f)),("side",new Vector3(1,0.05f,0)),("other",new Vector3(-1.2f,.6f,.9f)),("objective",new Vector3(-0.15f,.25f,1)),("eyepiece",new Vector3(0.15f,.2f,-1))};
   foreach(var (n,dir) in views){
    var target=n=="objective"?go.transform.TransformPoint(0,axis,b.max.z-0.02f):n=="eyepiece"?go.transform.TransformPoint(0,axis,b.min.z+0.02f):b.center;
    cam.transform.position=target+dir.normalized*b.extents.magnitude*(n=="objective"||n=="eyepiece"?1.0f:2.3f);cam.transform.LookAt(target);
    var rt=new RenderTexture(960,600,24,RenderTextureFormat.ARGB32){antiAliasing=4};cam.targetTexture=rt;cam.Render();RenderTexture.active=rt;
    var tex=new Texture2D(rt.width,rt.height,TextureFormat.RGB24,false);tex.ReadPixels(new Rect(0,0,rt.width,rt.height),0,0);tex.Apply();
    File.WriteAllBytes(Output+"/"+key+"_"+n+".png",tex.EncodeToPNG());cam.targetTexture=null;RenderTexture.active=null;
   }
   UnityEngine.Object.DestroyImmediate(go);bundle.Unload(true);
   Debug.Log("CLIPON_RENDER "+key);
  }
  Debug.Log("CLIPON_RENDER_CHECK_PASS");
 }
}
