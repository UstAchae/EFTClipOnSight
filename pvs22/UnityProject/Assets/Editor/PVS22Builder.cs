using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
public static class PVS22Builder {
 const string Src="Assets/PVS22Source", Gen="Assets/PVS22Generated", Out="D:/games/SPT-4.1.6/.codex-work/EFTClipOnSight/pvs22/built";
 public const string BundleKey="ustachae_pvs22/an_pvs22.bundle";
 [Serializable] public class Info {public float axisHeight,frontZ,rearZ,lensZ,lensRadius,objectiveZ;public float[] boundsMin,boundsMax;}
 static Vector3[] R3(BinaryReader r,int n){var a=new Vector3[n];for(int i=0;i<n;i++)a[i]=new Vector3(r.ReadSingle(),r.ReadSingle(),r.ReadSingle());return a;}
 static Vector2[] R2(BinaryReader r,int n){var a=new Vector2[n];for(int i=0;i<n;i++)a[i]=new Vector2(r.ReadSingle(),r.ReadSingle());return a;}
 static Texture2D Flat(string name,Color c,bool linear){
  var t=new Texture2D(4,4,TextureFormat.RGBA32,true,linear){name=name};t.SetPixels(Enumerable.Repeat(c,16).ToArray());t.Apply(true,false);
  AssetDatabase.CreateAsset(t,Gen+"/"+name+".asset");return t;
 }
 static Texture2D Import(string name,TextureImporterType type,bool srgb,TextureWrapMode wrap=TextureWrapMode.Repeat){
  string path=Src+"/"+name+".png";var im=(TextureImporter)AssetImporter.GetAtPath(path);
  im.textureType=type;im.sRGBTexture=srgb;im.mipmapEnabled=true;im.wrapMode=wrap;im.anisoLevel=4;im.SaveAndReimport();
  return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
 }
 // Standalone 1x sight, laid out like the Armasight Vulcan: an image lens on the output end, the optic
 // camera at the objective and the aim camera behind the lens. +Z is toward the muzzle. Thermal sights get
 // a ScopeThermalVisionData that finalize_clipons.py fills from the REAP-IR; the rest get night vision.
 public static void BuildSight(GameObject root,Shader stub,Shader liveShader,Material backGlass,string gen,float axisHeight,float lensZ0,float lensRadius,float objectiveZ,bool thermal){
  const float eyeRelief=0.074f;
  // The lens shader sizes its exit-pupil mask in object space for the native lens radius; a bigger disc
  // shows the image past the mask edge as a crescent. Keep the Vulcan's radius in the mesh and scale the node.
  const float r=0.016539544f;
  float y=axisHeight,lensZ=lensZ0-0.0005f,lensScale=lensRadius/r;

  // Same convention as the game's lens meshes: a disc in the local XZ plane facing local +Y, on a node
  // turned -90 degrees about X so +Y looks at the shooter. The lens shader works in that object space;
  // a disc facing local -Z renders black.
  const int seg=48;var disc=new Mesh{name="an_pvs22_linza"};
  var v=new Vector3[seg+1];var uv=new Vector2[seg+1];var n=new Vector3[seg+1];var t=new int[seg*3];
  v[0]=Vector3.zero;uv[0]=new Vector2(.5f,.5f);
  for(int i=0;i<seg;i++){float a=i*Mathf.PI*2/seg;v[i+1]=new Vector3(Mathf.Cos(a)*r,0,Mathf.Sin(a)*r);uv[i+1]=new Vector2(Mathf.Cos(a)*.5f+.5f,Mathf.Sin(a)*.5f+.5f);}
  for(int i=0;i<=seg;i++)n[i]=Vector3.up;
  // Faces local +Y: cross(b-a,c-a) must point along +Y.
  for(int i=0;i<seg;i++){t[i*3]=0;t[i*3+1]=1+(i+1)%seg;t[i*3+2]=1+i;}
  disc.vertices=v;disc.uv=uv;disc.normals=n;disc.triangles=t;disc.RecalculateTangents();disc.RecalculateBounds();
  AssetDatabase.CreateAsset(disc,gen+"/mesh_an_pvs22_linza.asset");

  var mark=new Texture2D(16,16,TextureFormat.RGBA32,false){name="tex_no_reticle"};mark.SetPixels(Enumerable.Repeat(new Color(0,0,0,0),256).ToArray());mark.Apply();
  AssetDatabase.CreateAsset(mark,gen+"/tex_no_reticle.asset");
  var lensMat=new Material(stub){name="an_pvs22_linza"};lensMat.SetTexture("_MarkTex",mark);AssetDatabase.CreateAsset(lensMat,gen+"/mat_linza.asset");

  var lens=new GameObject("linza");lens.transform.SetParent(root.transform,false);lens.transform.localPosition=new Vector3(0,y,lensZ);
  lens.transform.localRotation=new Quaternion(-0.7071068f,0,0,0.7071068f);lens.transform.localScale=new Vector3(lensScale,1,lensScale);
  lens.AddComponent<MeshFilter>().sharedMesh=disc;
  var lensRenderer=lens.AddComponent<MeshRenderer>();lensRenderer.sharedMaterial=lensMat;lensRenderer.shadowCastingMode=ShadowCastingMode.Off;

  // Eyepiece glass 3 mm behind the sight lens (far enough not to z-fight): wherever the sight lens shows
  // nothing, as in the item inspect view, the eyepiece reads as dark coated glass instead of an open tube.
  // Its normals form a convex dome so the reflection sweeps across it like on a real lens.
  var dome=new Mesh{name="an_pvs22_eyepiece_glass"};var dn=new Vector3[seg+1];
  for(int i=0;i<=seg;i++)dn[i]=(Vector3.up*2.5f*r+new Vector3(v[i].x,0,v[i].z)).normalized;
  dome.vertices=v;dome.uv=uv;dome.normals=dn;dome.triangles=t;dome.RecalculateTangents();dome.RecalculateBounds();
  AssetDatabase.CreateAsset(dome,gen+"/mesh_an_pvs22_eyepiece_glass.asset");
  var back=new GameObject("eyepiece_glass");back.transform.SetParent(root.transform,false);back.transform.localPosition=new Vector3(0,y,lensZ+0.003f);
  back.transform.localRotation=lens.transform.localRotation;back.transform.localScale=lens.transform.localScale;
  back.AddComponent<MeshFilter>().sharedMesh=dome;
  var backRenderer=back.AddComponent<MeshRenderer>();backRenderer.sharedMaterial=backGlass;backRenderer.shadowCastingMode=ShadowCastingMode.Off;

  // Live 1x picture for when no optic camera feeds the lens (a red dot or holo behind it, or at the hip):
  // the client renders the scene into _PVS22LiveTex. Whenever that picture is off (inspect view, other
  // players' weapons, eye off the axis) the disc draws dark coated glass, which also hides the sight lens's
  // own idle look. The client switches it off while an optic camera drives the sight lens. It sits 2 mm
  // nearer the eye than the sight lens so the two never z-fight.
  var liveMat=new Material(liveShader){name="an_pvs22_live"};AssetDatabase.CreateAsset(liveMat,gen+"/mat_live.asset");
  var live=new GameObject("pvs22_live");live.transform.SetParent(root.transform,false);live.transform.localPosition=new Vector3(0,y,lensZ-0.002f);
  live.transform.localRotation=lens.transform.localRotation;live.transform.localScale=lens.transform.localScale;
  live.AddComponent<MeshFilter>().sharedMesh=disc;
  var liveRenderer=live.AddComponent<MeshRenderer>();liveRenderer.sharedMaterial=liveMat;liveRenderer.shadowCastingMode=ShadowCastingMode.Off;liveRenderer.receiveShadows=false;

  // Carries the tube image effect's shader in the bundle (the client reads it from here); never drawn.
  var tubeMat=new Material(WriteTubeShader(gen)){name="an_pvs22_tube"};AssetDatabase.CreateAsset(tubeMat,gen+"/mat_tube.asset");
  var tubeNode=new GameObject("pvs22_tube");tubeNode.transform.SetParent(root.transform,false);
  var tubeRenderer=tubeNode.AddComponent<MeshRenderer>();tubeRenderer.sharedMaterial=tubeMat;tubeRenderer.enabled=false;
  var blurMat=new Material(WriteBlurShader(gen)){name="an_pvs22_blur"};AssetDatabase.CreateAsset(blurMat,gen+"/mat_blur.asset");
  var blurNode=new GameObject("pvs22_blur");blurNode.transform.SetParent(root.transform,false);
  var blurRenderer=blurNode.AddComponent<MeshRenderer>();blurRenderer.sharedMaterial=blurMat;blurRenderer.enabled=false;

  var aim=new GameObject("mod_aim_camera");aim.transform.SetParent(root.transform,false);
  aim.transform.localPosition=new Vector3(0,y,lensZ-eyeRelief);aim.transform.localRotation=new Quaternion(0,1,0,0);

  var cam=new GameObject("optic_camera");cam.layer=8;cam.transform.SetParent(root.transform,false);cam.transform.localPosition=new Vector3(0,y,objectiveZ+0.002f);
  var scope=cam.AddComponent<EFT.CameraControl.ScopeData>();
  var camData=cam.AddComponent<EFT.CameraControl.ScopeCameraData>();
  camData.FieldOfView=23f;camData.NearClipPlane=0.05f;camData.FarClipPlane=1000f;camData.OpticCullingMask=true;camData.OpticCullingMaskScale=1f;
  var fx=cam.AddComponent<EFT.CameraControl.ScopeEffectsData>();
  if(thermal){
   // REAP-IR's effects; its thermal data is copied in by finalize_clipons.py.
   fx.ChromaticAberration=true;fx.ChromaticAberrationAniso=2;fx.ChromaticAberrationShift=0.02051f;fx.BloomOptimized=true;fx.BloomOptimizedIntensity=0.4f;fx.BloomOptimizedThreshold=0.272f;fx.BloomOptimizedBlurSize=5.5f;
   var tv=cam.AddComponent<EFT.CameraControl.ScopeThermalVisionData>();tv.ThermalVision=true;
   scope.ThermalVisionData=tv;
  }else{
   fx.ChromaticAberration=true;fx.ChromaticAberrationAniso=3;fx.ChromaticAberrationShift=0.00583f;fx.FastVignette=true;fx.UltimateBloom=true;
   fx.White=1.76f;fx.AdaptionSpeed=3f;fx.ExposureAdjustment=0.03f;fx.MiddleGrey=0.15f;fx.AdaptiveTextureSize=256;fx.Type=5;
   var nv=cam.AddComponent<EFT.CameraControl.ScopeNightVisionData>();
   nv.NightVision=true;nv.Intensity=2f;nv.MaskSize=1.5f;nv.NoiseIntensity=0.05f;nv.NoiseScale=5f;nv.Color=new Color(0.13f,0.36f,0.13f,0);
   scope.NightVisionData=nv;
  }
  scope.PostEffectsData=fx;
  cam.SetActive(false);

  var sight=root.AddComponent<EFT.CameraControl.OpticSight>();sight.enabled=false;
  sight.LensRenderer=lensRenderer;sight.ScopeTransform=aim.transform;sight.DistanceToCamera=eyeRelief;sight.ScopeData=scope;
  var cache=root.AddComponent<ScopePrefabCache>();cache.AngleByRange=new ScopePrefabCache.DistaneAngle[0];
  cache._scopeModeInfos=new[]{new ScopePrefabCache.ScopeModeInfo{ModeGameObject=root,OpticSight=sight}};
 }
 // Stub shader; the finalize scripts point every material at the game's p0 reflective shader.
 public static Shader WriteStubShader(string gen){
  File.WriteAllText(gen+"/PVS22Stub.shader","Shader \"UstAchae/PVS22/Stub\" { Properties { _MainTex (\"m\", 2D) = \"white\" {} _SpecMap (\"s\", 2D) = \"white\" {} _BumpMap (\"b\", 2D) = \"bump\" {} _MarkTex (\"r\", 2D) = \"black\" {} _MaskTex (\"k\", 2D) = \"white\" {} _MaskTex2 (\"k2\", 2D) = \"white\" {} _Color (\"c\", Color) = (1,1,1,1) } SubShader { Pass { Color (1,1,1,1) } } }");
  AssetDatabase.ImportAsset(gen+"/PVS22Stub.shader",ImportAssetOptions.ForceSynchronousImport);
  return AssetDatabase.LoadAssetAtPath<Shader>(gen+"/PVS22Stub.shader");
 }
 // The live eyepiece shader ships in the bundle as is (same Unity version as the game). It samples the
 // client's render texture in screen space, so the picture lines up 1x with the world around the eyepiece.
 // Night vision (_PVS22LiveMode 0): the tube's gain, phosphor tint and noise. Thermal (1): the texture holds
 // the scene's heat buffer, mapped white-hot. _PVS22LiveOn (per renderer) fades it to black.

 // The tube model both night-vision pictures use (see the comment at the top of PVS22Tube.cginc).
 public static void WriteTubeInclude(string gen){
  File.WriteAllText(gen+"/PVS22Tube.cginc",@"// Image-intensifier model shared by the clip-ons' eyepiece picture and their optic-camera effect. Our own
// implementation of the usual tube model (as in BRNVG): the scene is weighted by the photocathode's
// spectral response and amplified, then the output carries read noise plus shot noise that grows with the
// square root of the signal, a coarser grain, a stationary fixed-pattern gain variation and brief 1-pixel
// scintillation sparkles, refreshed at a set rate and strongest in the dark; finally the phosphor colour.
#ifndef PVS22_TUBE_INCLUDED
#define PVS22_TUBE_INCLUDED
float4 _PVS22TubeParams;   // x gain, y noise scale, z grain size in pixels, w time
float4 _PVS22TubeTint;     // phosphor colour, peak 1
float4 _PVS22TubeSpectral; // photocathode weights for the scene's r, g, b

float pvs22_hash12(float2 p) { float3 p3 = frac(p.xyx * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return frac((p3.x + p3.y) * p3.z); }
float pvs22_hash13(float3 p3) { p3 = frac(p3 * 0.1031); p3 += dot(p3, p3.zyx + 31.32); return frac((p3.x + p3.y) * p3.z); }
// Roughly normal (sum of three uniforms), zero mean, unit variance.
float pvs22_gauss(float2 cell, float frame) {
    return (pvs22_hash13(float3(cell, frame)) + pvs22_hash13(float3(cell + 71.3, frame)) + pvs22_hash13(float3(cell + 143.7, frame)) - 1.5) * 2.0;
}
float pvs22_value(float2 p) {
    float2 i = floor(p), f = frac(p); f = f * f * (3 - 2 * f);
    return lerp(lerp(pvs22_hash12(i), pvs22_hash12(i + float2(1, 0)), f.x), lerp(pvs22_hash12(i + float2(0, 1)), pvs22_hash12(i + 1), f.x), f.y);
}

// pixel: position in output pixels. Returns the phosphor colour for the scene colour at that pixel.
float3 pvs22_tube(float3 scene, float2 pixel) {
    float3 w = max(_PVS22TubeSpectral.rgb, 0); w /= max(dot(w, 1), 1e-4);
    float lum = dot(max(scene, 0), w);
    float tube = 1 - exp(-lum * _PVS22TubeParams.x);           // amplified, soft-saturating screen brightness
    float frame = floor(_PVS22TubeParams.w * 30.0);              // noise refreshes 30 times a second
    float grain = max(_PVS22TubeParams.z, 0.5);
    float dark = 1 - 0.65 * tube;                                // noise shows most in the dark
    float k = _PVS22TubeParams.y;
    // Stationary gain variation of the tube.
    float fixedPattern = (pvs22_value(pixel / 48 + 17.1) - 0.5) * 2 + (pvs22_hash12(floor(pixel / 5) + 91.7) - 0.5) * 0.45;
    tube *= 1 + fixedPattern * 0.018 * k;
    // Read noise plus shot noise, and a coarser grain.
    float sigma = 0.03 + 0.065 * sqrt(max(tube, 0.001));
    float n = pvs22_gauss(floor(pixel / grain), frame) * sigma + pvs22_gauss(floor(pixel / (grain * 3)), floor(frame * 0.53) + 137) * 0.022;
    // Scintillation: now and then a single bright pixel in a 3x3 tile.
    float2 tile = floor(pixel / 3);
    float event = step(1 - 0.0015, pvs22_hash13(float3(tile, frame)));
    float2 at = floor(float2(pvs22_hash13(float3(tile + 17.3, frame)), pvs22_hash13(float3(tile.yx + 43.7, frame))) * 3);
    float2 inTile = floor(pixel) - tile * 3;
    float spark = event * step(dot(abs(inTile - at), 1), 0.5) * 0.35 * (1.25 - saturate(tube));
    tube = max(tube + (n * k + spark * k) * dark, 0);
    return saturate(tube * _PVS22TubeTint.rgb);
}
#endif
");
 }
 // Image effect for the optic camera when a night-vision clip-on sits in front of the scope (or is the
 // sight): it replaces the game's night vision. Shipped in the bundle on the hidden "pvs22_tube" renderer.
 public static Shader WriteTubeShader(string gen){
  WriteTubeInclude(gen);
  File.WriteAllText(gen+"/PVS22Tube.shader",@"Shader ""UstAchae/PVS22/Tube"" {
 Properties { _MainTex (""source"", 2D) = ""white"" {} }
 SubShader {
  Cull Off ZWrite Off ZTest Always
  Pass {
   CGPROGRAM
   #pragma vertex vert_img
   #pragma fragment frag
   #include ""UnityCG.cginc""
   #include ""PVS22Tube.cginc""
   sampler2D _MainTex;
   float4 _MainTex_TexelSize;
   fixed4 frag (v2f_img i) : SV_Target {
    return fixed4(pvs22_tube(tex2D(_MainTex, i.uv).rgb, i.uv * _MainTex_TexelSize.zw), 1);
   }
   ENDCG
  }
 }
}");
  AssetDatabase.ImportAsset(gen+"/PVS22Tube.cginc",ImportAssetOptions.ForceSynchronousImport);
  AssetDatabase.ImportAsset(gen+"/PVS22Tube.shader",ImportAssetOptions.ForceSynchronousImport);
  return AssetDatabase.LoadAssetAtPath<Shader>(gen+"/PVS22Tube.shader");
 }
 // Soft blur for a day scope magnifying past the clip-on's rating: a 16-tap disc whose radius is set in
 // pixels and grows continuously from zero (the game's optimized blur only steps by whole passes). The
 // client runs it twice with the disc turned, for a smoother result. Carried on the hidden "pvs22_blur".
 public static Shader WriteBlurShader(string gen){
  File.WriteAllText(gen+"/PVS22Blur.shader",@"Shader ""UstAchae/PVS22/Blur"" {
 Properties { _MainTex (""source"", 2D) = ""white"" {} }
 SubShader {
  Cull Off ZWrite Off ZTest Always
  Pass {
   CGPROGRAM
   #pragma vertex vert_img
   #pragma fragment frag
   #include ""UnityCG.cginc""
   sampler2D _MainTex;
   float4 _MainTex_TexelSize;
   float4 _PVS22Blur; // x radius in source pixels, y disc rotation in radians
   static const float2 disc[16] = {
    float2(-0.613, 0.617), float2(0.170, -0.040), float2(-0.299, 0.791), float2(0.645, 0.493),
    float2(-0.651, 0.718), float2(0.421, 0.027), float2(-0.818, -0.200), float2(-0.360, -0.946),
    float2(0.234, 0.719), float2(0.098, -0.470), float2(0.488, -0.844), float2(0.833, -0.226),
    float2(-0.142, 0.155), float2(-0.474, 0.267), float2(0.909, 0.330), float2(-0.081, -0.927) };
   fixed4 frag (v2f_img i) : SV_Target {
    float c = cos(_PVS22Blur.y), s = sin(_PVS22Blur.y);
    float2 step = _MainTex_TexelSize.xy * _PVS22Blur.x;
    float4 sum = tex2D(_MainTex, i.uv); float weight = 1;
    [unroll] for (int k = 0; k < 16; k++) {
     float2 o = float2(disc[k].x * c - disc[k].y * s, disc[k].x * s + disc[k].y * c);
     float w = exp(-2 * dot(o, o));
     sum += tex2D(_MainTex, i.uv + o * step) * w; weight += w;
    }
    return sum / weight;
   }
   ENDCG
  }
 }
}");
  AssetDatabase.ImportAsset(gen+"/PVS22Blur.shader",ImportAssetOptions.ForceSynchronousImport);
  return AssetDatabase.LoadAssetAtPath<Shader>(gen+"/PVS22Blur.shader");
 }
 public static Shader WriteLiveShader(string gen){
  WriteTubeInclude(gen);
  File.WriteAllText(gen+"/PVS22Live.shader",@"Shader ""UstAchae/PVS22/Live"" {
 Properties { _PVS22LiveOn (""on"", Range(0,1)) = 0 _PVS22LiveMode (""mode"", Range(0,1)) = 0 _PVS22LiveFov (""fov"", Float) = 10 }
 SubShader {
  Tags { ""Queue""=""Geometry"" ""RenderType""=""Opaque"" }
  Cull Off
  Pass {
   CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #include ""UnityCG.cginc""
   #include ""PVS22Tube.cginc""
   sampler2D _PVS22LiveTex;
   float4 _PVS22LiveTex_TexelSize;
   float4 _PVS22ThermalParams; // x cold level, y gain
   float _PVS22LiveOn;
   float _PVS22LiveMode;
   float _PVS22LiveFov;
   struct v2f { float4 pos : SV_POSITION; float4 screen : TEXCOORD0; float2 uv : TEXCOORD1; float3 normal : TEXCOORD2; float3 view : TEXCOORD3; float3 world : TEXCOORD4; };
   v2f vert (appdata_base v) {
    v2f o; o.pos = UnityObjectToClipPos(v.vertex); o.screen = ComputeScreenPos(o.pos); o.uv = v.texcoord.xy;
    o.normal = UnityObjectToWorldNormal(v.normal); o.view = WorldSpaceViewDir(v.vertex);
    o.world = mul(unity_ObjectToWorld, v.vertex).xyz; return o;
   }
   // The eyepiece is focused at infinity, so its field stop is too: seen from a distance the picture shows only
   // along view directions within the device's field of view of its axis, and an edge sweeps across the whole lens
   // as the eye moves off the axis, black beyond. The disc faces +Y toward the shooter.
   float fieldStop(float3 world) {
    float3 n = normalize(mul((float3x3)unity_ObjectToWorld, float3(0, 1, 0)));
    float c = -dot(normalize(world - _WorldSpaceCameraPos), n);
    if (c <= 0) return 0;
    float halfFov = _PVS22LiveFov * 0.5;
    return 1 - smoothstep(halfFov - 0.5, halfFov + 0.2, degrees(acos(saturate(c))));
   }
   fixed4 frag (v2f i) : SV_Target {
    float2 uv = i.screen.xy / i.screen.w;
    float3 scene = tex2D(_PVS22LiveTex, uv).rgb;
    float2 pixel = uv * _PVS22LiveTex_TexelSize.zw;
    float lum = dot(scene, float3(0.299, 0.587, 0.114));
    float3 picture = _PVS22LiveMode > 0.5
        ? saturate((lum - _PVS22ThermalParams.x) * _PVS22ThermalParams.y).xxx
        : pvs22_tube(scene, pixel);
    // Off (no live picture: a magnified optic behind it, other weapons, the inspect view): near-black coated
    // glass with only a faint sheen at grazing angles, like an unlit eyepiece.
    float grazing = pow(1 - abs(dot(normalize(i.normal), normalize(i.view))), 5);  // the disc is drawn from either side
    float3 glass = float3(0.004, 0.005, 0.008) + float3(0.10, 0.12, 0.16) * grazing;
    return fixed4(lerp(glass, picture, _PVS22LiveOn * fieldStop(i.world)), 1);
   }
   ENDCG
  }
 }
}");
  AssetDatabase.ImportAsset(gen+"/PVS22Live.shader",ImportAssetOptions.ForceSynchronousImport);
  return AssetDatabase.LoadAssetAtPath<Shader>(gen+"/PVS22Live.shader");
 }
 // Coated objective glass, shipped in the bundle like the live shader. The lens UVs are radial (centre 0.5,
 // rim at distance 0.5). Layers, from the photos of these sights: a near-black body, a thin-film anti-reflection
 // coating whose reflected colour shifts from _CoatColor head-on to _CoatGrazing at grazing angles, the game's
 // crisp cubemap (finalize points _Cube at it) seen through that coating, a few lens elements inside the barrel
 // drawn with parallax (their rims and highlight arcs slide against each other as the view turns), and a
 // Fresnel rim. Opaque, so the hollow tube never shows through.
 public static Shader WriteLensShader(string gen){
  File.WriteAllText(gen+"/PVS22Lens.shader",@"Shader ""UstAchae/PVS22/Lens"" {
 Properties {
  _Cube (""reflection"", Cube) = """" {}
  _CoatColor (""coating head-on"", Color) = (0.30, 0.22, 0.95, 1)
  _CoatGrazing (""coating grazing"", Color) = (0.95, 0.35, 0.60, 1)
  _ElementColor (""inner elements"", Color) = (0.35, 0.45, 1.0, 1)
  _Base (""body"", Color) = (0.004, 0.005, 0.012, 1)
  _Reflect (""reflection strength"", Range(0, 2)) = 0.9
  _Elements (""inner element strength"", Range(0, 2)) = 1
 }
 SubShader {
  Tags { ""Queue""=""Geometry"" ""RenderType""=""Opaque"" }
  Cull Off
  Pass {
   CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #include ""UnityCG.cginc""
   samplerCUBE _Cube;
   float4 _CoatColor, _CoatGrazing, _ElementColor, _Base;
   float _Reflect, _Elements;
   struct v2f { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; float3 viewT : TEXCOORD1; float3 normalW : TEXCOORD2; float3 viewW : TEXCOORD3; };
   v2f vert (appdata_tan v) {
    v2f o; o.pos = UnityObjectToClipPos(v.vertex); o.uv = v.texcoord.xy;
    TANGENT_SPACE_ROTATION;
    o.viewT = mul(rotation, ObjSpaceViewDir(v.vertex));
    o.normalW = UnityObjectToWorldNormal(v.normal); o.viewW = WorldSpaceViewDir(v.vertex);
    return o;
   }
   float ring (float2 p, float r, float w) { float d = (length(p) - r) / w; return exp(-d * d); }
   float blob (float2 p, float2 c, float s) { float2 d = p - c; return exp(-dot(d, d) * s); }
   fixed4 frag (v2f i) : SV_Target {
    float2 p = (i.uv - 0.5) * 2;                  // lens plane, rim at radius 1
    // Double-sided glass: turn the normal toward the viewer whichever side is drawn.
    float3 vt = normalize(i.viewT); vt.z = abs(vt.z);
    float3 n = normalize(i.normalW), v = normalize(i.viewW);
    if (dot(n, v) < 0) n = -n;
    float cosv = saturate(dot(n, v));
    float fres = pow(1 - cosv, 3);
    float3 coat = lerp(_CoatColor.rgb, _CoatGrazing.rgb, saturate(fres * 1.2));
    // The scene in the front surface, tinted by the coating's residual reflection (a few percent head-on).
    float3 env = texCUBE(_Cube, reflect(-v, n)).rgb;
    float3 col = _Base.rgb + env * coat * (0.03 + 0.55 * fres) * _Reflect;
    // Inner elements: each sits deeper, so its picture shifts further against the front glass with the view.
    float2 shift = vt.xy / max(vt.z, 0.25);
    float3 inner = 0;
    // Irregular elements, as real lens groups are: depth, rim radius and strength per element. Only the rim's
    // lit side shows (light from the upper left, like the window highlight), so head-on they read as a few
    // uneven arcs rather than even ripples; the light's ghost images stay the brightest part.
    const float4 elements[4] = {
     float4(0.16, 0.90, 1.00, 0.0),   // depth, rim radius, strength, arc offset (radians)
     float4(0.41, 0.71, 0.55, 0.6),
     float4(0.58, 0.83, 0.35, -0.5),
     float4(0.87, 0.52, 0.45, 0.3) };
    const float2 light = normalize(float2(-0.66, 0.75));
    [unroll] for (int k = 0; k < 4; k++) {
     float4 e = elements[k];
     float2 q = p + shift * e.x;
     float3 tone = k % 2 == 0 ? _ElementColor.rgb : lerp(_ElementColor.rgb, _CoatGrazing.rgb, 0.45);
     float2 dir = q / max(length(q), 1e-4);
     float ca = cos(e.w), sa = sin(e.w);
     float2 lk = float2(light.x * ca - light.y * sa, light.x * sa + light.y * ca);
     float arc = pow(saturate(dot(dir, lk) * 0.5 + 0.5), 6);      // a lit segment, not a full circle
     inner += tone * e.z * (0.8 * ring(q, e.y, 0.012) * arc            // element rim, thin and partial
                         + 1.2 * blob(q, -lk * e.y * 0.38, 55)         // ghost of the light on the element
                         + 0.4 * blob(q, lk * e.y * 0.22, 130));       // its second surface, smaller and dimmer
    }
    // Elements only show inside the barrel, and fade toward the front rim.
    col += inner * 0.4 * _Elements * (1 - smoothstep(0.85, 1.0, length(p)));
    // Crisp window highlight on the front surface, moving with the view like a real reflection.
    col += float3(0.85, 0.88, 1.0) * 0.6 * blob(p - shift * 0.05, float2(-0.42, 0.45), 160);
    col += coat * 0.25 * fres;                       // coloured Fresnel rim
    return fixed4(col, 1);
   }
   ENDCG
  }
 }
}");
  AssetDatabase.ImportAsset(gen+"/PVS22Lens.shader",ImportAssetOptions.ForceSynchronousImport);
  return AssetDatabase.LoadAssetAtPath<Shader>(gen+"/PVS22Lens.shader");
 }
 // Glass material on the lens shader; the coating colours default to blue-violet night-vision glass.
 public static Material LensMaterial(Shader lens,string name,Color? coat=null,Color? grazing=null,Color? elements=null){
  var m=new Material(lens){name=name};
  if(coat!=null)m.SetColor("_CoatColor",coat.Value);
  if(grazing!=null)m.SetColor("_CoatGrazing",grazing.Value);
  if(elements!=null)m.SetColor("_ElementColor",elements.Value);
  return m;
 }
 public static void Build(){
  PlayerSettings.colorSpace=ColorSpace.Linear;
  if(AssetDatabase.IsValidFolder(Gen))AssetDatabase.DeleteAsset(Gen);
  Directory.CreateDirectory(Gen);Directory.CreateDirectory(Out);AssetDatabase.Refresh();
  var info=JsonUtility.FromJson<Info>(File.ReadAllText(Src+"/pvs22.json"));

  var mesh=new Mesh{name="an_pvs22",indexFormat=IndexFormat.UInt32};
  using(var r=new BinaryReader(File.OpenRead(Src+"/pvs22.bin"))){
   int n=r.ReadInt32(),f=r.ReadInt32(),s=r.ReadInt32();
   mesh.vertices=R3(r,n);mesh.normals=R3(r,n);mesh.uv=R2(r,n);mesh.subMeshCount=s;
   for(int i=0;i<s;i++){var a=new int[r.ReadInt32()];for(int j=0;j<a.Length;j++)a[j]=r.ReadInt32();mesh.SetTriangles(a,i,true);}
   if(r.BaseStream.Position!=r.BaseStream.Length)throw new Exception("Unread mesh bytes");
  }
  mesh.RecalculateTangents();mesh.RecalculateBounds();mesh.UploadMeshData(false);
  AssetDatabase.CreateAsset(mesh,Gen+"/mesh_an_pvs22.asset");

  var label=Import("label",TextureImporterType.Default,true,TextureWrapMode.Clamp);
  var white=Flat("tex_white",Color.white,false);
  var matte=Flat("tex_white_matte",new Color(1,1,1,.1f),false);
  var spec=Flat("tex_spec",new Color(.35f,.35f,.35f,1),false);
  var bump=Flat("tex_flat_normal",new Color(.5f,.5f,1,1),true);
  Texture2D metalA=Import("metal_albedo",TextureImporterType.Default,true),metalS=Import("metal_spec",TextureImporterType.Default,false),metalN=Import("metal_normal",TextureImporterType.NormalMap,false);
  Texture2D rubberA=Import("rubber_albedo",TextureImporterType.Default,true),rubberS=Import("rubber_spec",TextureImporterType.Default,false),rubberN=Import("rubber_normal",TextureImporterType.NormalMap,false);

  var stub=WriteStubShader(Gen);
  var liveShader=WriteLiveShader(Gen);
  var lensShader=WriteLensShader(Gen);
  string[] names={"body","label","text","glass","rubber","black"};
  var mats=names.Select(n=>{
   // The PVS-22's objective reads pale silver in photos: a near-neutral coating and a stronger reflection.
   var m=n=="glass"?LensMaterial(lensShader,"an_pvs22_glass",new Color(0.58f,0.60f,0.72f),new Color(0.78f,0.72f,0.86f),new Color(0.72f,0.76f,0.92f)):new Material(stub){name="an_pvs22_"+n};
   if(n=="glass"){m.SetFloat("_Reflect",1.8f);m.SetColor("_Base",new Color(0.02f,0.021f,0.026f));}
   switch(n){
    case "body":m.SetTexture("_MainTex",metalA);m.SetTexture("_SpecMap",metalS);m.SetTexture("_BumpMap",metalN);break;
    case "rubber":m.SetTexture("_MainTex",rubberA);m.SetTexture("_SpecMap",rubberS);m.SetTexture("_BumpMap",rubberN);break;
    default:m.SetTexture("_MainTex",n=="label"?label:n=="text"||n=="black"?matte:white);m.SetTexture("_SpecMap",n=="glass"?white:spec);m.SetTexture("_BumpMap",bump);break;
   }
   AssetDatabase.CreateAsset(m,Gen+"/mat_"+n+".asset");return m;}).ToArray();

  var root=new GameObject("an_pvs22");
  var pivot=root.AddComponent<PreviewPivot>();
  var lo=new Vector3(info.boundsMin[0],info.boundsMin[1],info.boundsMin[2]);var hi=new Vector3(info.boundsMax[0],info.boundsMax[1],info.boundsMax[2]);
  pivot.pivotPosition=(lo+hi)/2;pivot.pivotRotation=new Quaternion(0,0.7071068f,0,0.7071068f);pivot.scale=Vector3.one;
  pivot.Icon=new PreviewPivot.IconSettings{rotation=new Quaternion(0,0.8433914f,0,-0.5372996f),boundsScale=0.9f,perspective=15,orthographicSize=10};
  var body=new GameObject("an_pvs22_LOD0");body.transform.SetParent(root.transform,false);
  body.AddComponent<MeshFilter>().sharedMesh=mesh;
  var mr=body.AddComponent<MeshRenderer>();mr.sharedMaterials=mats;mr.shadowCastingMode=ShadowCastingMode.On;mr.receiveShadows=true;
  // Disabled like the native mods' colliders: the game only reads it to size the loot collider when dropped.
  var box=body.AddComponent<BoxCollider>();box.center=(lo+hi)/2;box.size=hi-lo;box.enabled=false;
  // Markers the client plugin uses to find the clip-on on a weapon and measure it against the optic.
  var front=new GameObject("pvs22_front");front.transform.SetParent(root.transform,false);front.transform.localPosition=new Vector3(0,info.axisHeight,info.frontZ);
  var rear=new GameObject("pvs22_rear");rear.transform.SetParent(root.transform,false);rear.transform.localPosition=new Vector3(0,info.axisHeight,info.rearZ);
  BuildSight(root,stub,liveShader,mats[Array.IndexOf(names,"glass")],Gen,info.axisHeight,info.lensZ,info.lensRadius,info.objectiveZ,false);
  string prefab=Gen+"/an_pvs22.prefab";PrefabUtility.SaveAsPrefabAsset(root,prefab);UnityEngine.Object.DestroyImmediate(root);
  AssetDatabase.SaveAssets();

  var build=new AssetBundleBuild{assetBundleName=BundleKey,assetNames=new[]{prefab}};
  if(BuildPipeline.BuildAssetBundles(Out,new[]{build},BuildAssetBundleOptions.ChunkBasedCompression|BuildAssetBundleOptions.StrictMode,BuildTarget.StandaloneWindows64)==null)throw new Exception("Build failed");
  Debug.Log("PVS22_BUILD_SUCCESS");
 }
}
