using System;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;
public static class PVS22RenderCheck {
 const string Root="D:/games/SPT-4.1.6";
 const string Bundle=Root+"/.codex-work/EFTClipOnSight/pvs22/package/bundles/"+PVS22Builder.BundleKey;
 const string Output=Root+"/.codex-work/EFTClipOnSight/pvs22/previews";
 public static void Run(){
  Directory.CreateDirectory(Output);
  AssetBundle.LoadFromFile(Root+"/EscapeFromTarkov_Data/StreamingAssets/Windows/shaders");
  AssetBundle.LoadFromFile(Root+"/EscapeFromTarkov_Data/StreamingAssets/Windows/cubemaps");
  var bundle=AssetBundle.LoadFromFile(Bundle);if(bundle==null)throw new Exception("Bundle failed to load");
  RenderSettings.ambientMode=AmbientMode.Trilight;
  RenderSettings.ambientSkyColor=new Color(.45f,.48f,.55f);RenderSettings.ambientEquatorColor=new Color(.28f,.28f,.29f);RenderSettings.ambientGroundColor=new Color(.12f,.12f,.13f);
  var l=new GameObject("key").AddComponent<Light>();l.type=LightType.Directional;l.intensity=1.3f;l.transform.rotation=Quaternion.Euler(35,-35,0);
  var fill=new GameObject("fill").AddComponent<Light>();fill.type=LightType.Directional;fill.intensity=.5f;fill.transform.rotation=Quaternion.Euler(20,140,0);
  var cam=new GameObject("camera").AddComponent<Camera>();cam.clearFlags=CameraClearFlags.SolidColor;cam.backgroundColor=new Color(.55f,.58f,.62f);cam.fieldOfView=30;cam.nearClipPlane=.001f;cam.farClipPlane=100;cam.aspect=1.6f;
  var go=UnityEngine.Object.Instantiate(bundle.LoadAsset<GameObject>(bundle.GetAllAssetNames().Single(x=>x.EndsWith(".prefab"))));
  foreach(var r in go.GetComponentsInChildren<Renderer>())foreach(var m in r.sharedMaterials)if(m==null||!m.shader.isSupported)throw new Exception("Unsupported material "+(m==null?"null":m.name+" "+m.shader.name));
  var shaders=string.Join(",",go.GetComponentsInChildren<Renderer>().SelectMany(r=>r.sharedMaterials).Select(m=>m.shader.name).Distinct());
  var b=go.GetComponentInChildren<Renderer>().bounds;
  var views=new[]{("iso",new Vector3(1.2f,.7f,-1f)),("side",new Vector3(1,0.05f,0)),("rear",new Vector3(0.25f,.15f,-1)),("front",new Vector3(-0.3f,.25f,1)),("objective",new Vector3(-0.15f,.35f,1)),("eye_l",new Vector3(.6f,.1f,-1)),("eye_r",new Vector3(-.6f,.1f,-1)),("eye_up",new Vector3(0,.6f,-1)),("eye_dn",new Vector3(.1f,-.5f,-1)),("boot_a",new Vector3(.9f,.6f,-.5f)),("boot_b",new Vector3(-.9f,.6f,-.5f)),("boot_c",new Vector3(.2f,1,-.15f)),("boot_d",new Vector3(.9f,-.2f,-.3f)),("tube",new Vector3(1,.45f,-.55f)),("tube_flat",new Vector3(1,.45f,-.55f)),("tube_smooth",new Vector3(1,.45f,-.55f))};
  foreach(var (n,dir) in views){
   if(n=="tube_flat"){var flat=new Texture2D(4,4,TextureFormat.RGBA32,false,true);flat.SetPixels(Enumerable.Repeat(new Color(.5f,.5f,1,1),16).ToArray());flat.Apply();foreach(var r in go.GetComponentsInChildren<Renderer>())foreach(var m in r.sharedMaterials)if(m.HasProperty("_BumpMap"))m.SetTexture("_BumpMap",flat);}
   if(n=="tube_smooth"){foreach(var r in go.GetComponentsInChildren<Renderer>())foreach(var m in r.sharedMaterials){if(m.HasProperty("_Glossness"))m.SetFloat("_Glossness",.6f);if(m.HasProperty("_ReflectColor"))m.SetColor("_ReflectColor",Color.black);}}
   bool eye=n.StartsWith("eye")||n.StartsWith("boot")||n.StartsWith("tube");var target=n=="objective"?go.transform.TransformPoint(0,.04f,.14f):eye?go.transform.TransformPoint(0,.04f,-.01f):b.center;cam.transform.position=target+dir.normalized*b.extents.magnitude*(n=="objective"?1.1f:eye?1.0f:2.3f);cam.transform.LookAt(target);
   var rt=new RenderTexture(960,600,24,RenderTextureFormat.ARGB32){antiAliasing=4};cam.targetTexture=rt;cam.Render();RenderTexture.active=rt;
   var tex=new Texture2D(rt.width,rt.height,TextureFormat.RGB24,false);tex.ReadPixels(new Rect(0,0,rt.width,rt.height),0,0);tex.Apply();
   File.WriteAllBytes(Output+"/"+n+".png",tex.EncodeToPNG());cam.targetTexture=null;RenderTexture.active=null;
  }
  Debug.Log("PVS22_RENDER_CHECK_PASS shaders="+shaders);
 }
}
