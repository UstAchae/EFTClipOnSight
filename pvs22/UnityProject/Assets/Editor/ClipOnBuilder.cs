using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
// Builds one bundle per textured clip-on that clipons/prepare.py set up in Assets/ClipOnSource/<key>:
// the model with its own PBR-derived maps, the markers the client plugin reads, and the same 1x sight rig
// as the PVS-22 (night vision, or thermal for the UTC). Run: -executeMethod ClipOnBuilder.Build
public static class ClipOnBuilder {
 const string Src="Assets/ClipOnSource",Gen="Assets/ClipOnGenerated",Out="D:/games/SPT-4.1.6/.codex-work/EFTClipOnSight/clipons/built";
 [Serializable] public class Info {public string key;public float axisHeight,frontZ,rearZ,lensZ,lensRadius,objectiveZ,fov;public bool thermal;public float[] boundsMin,boundsMax;}
 static Vector3[] R3(BinaryReader r,int n){var a=new Vector3[n];for(int i=0;i<n;i++)a[i]=new Vector3(r.ReadSingle(),r.ReadSingle(),r.ReadSingle());return a;}
 static Vector2[] R2(BinaryReader r,int n){var a=new Vector2[n];for(int i=0;i<n;i++)a[i]=new Vector2(r.ReadSingle(),r.ReadSingle());return a;}
 static Texture2D Import(string path,TextureImporterType type,bool srgb){
  var im=(TextureImporter)AssetImporter.GetAtPath(path);
  im.textureType=type;im.sRGBTexture=srgb;im.mipmapEnabled=true;im.wrapMode=TextureWrapMode.Repeat;im.anisoLevel=4;im.maxTextureSize=2048;im.SaveAndReimport();
  return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
 }
 static Texture2D Flat(string gen,string name,Color c,bool linear){
  var t=new Texture2D(4,4,TextureFormat.RGBA32,true,linear){name=name};t.SetPixels(Enumerable.Repeat(c,16).ToArray());t.Apply(true,false);
  AssetDatabase.CreateAsset(t,gen+"/"+name+".asset");return t;
 }
 public static string BundleKey(string key)=>"ustachae_clipons/"+key+".bundle";

 public static void Build(){
  PlayerSettings.colorSpace=ColorSpace.Linear;
  if(AssetDatabase.IsValidFolder(Gen))AssetDatabase.DeleteAsset(Gen);
  Directory.CreateDirectory(Gen);Directory.CreateDirectory(Out);AssetDatabase.Refresh();
  var builds=Directory.GetDirectories(Src).Select(d=>BuildOne(Path.GetFileName(d))).ToArray();
  AssetDatabase.SaveAssets();
  if(BuildPipeline.BuildAssetBundles(Out,builds,BuildAssetBundleOptions.ChunkBasedCompression|BuildAssetBundleOptions.StrictMode,BuildTarget.StandaloneWindows64)==null)throw new Exception("Build failed");
  Debug.Log("CLIPON_BUILD_SUCCESS "+string.Join(",",builds.Select(b=>b.assetBundleName)));
 }

 static AssetBundleBuild BuildOne(string key){
  string src=Src+"/"+key,gen=Gen+"/"+key;Directory.CreateDirectory(gen);AssetDatabase.Refresh();
  var info=JsonUtility.FromJson<Info>(File.ReadAllText(src+"/info.json"));
  string name="ustachae_"+key;

  var mesh=new Mesh{name=name,indexFormat=IndexFormat.UInt32};
  using(var r=new BinaryReader(File.OpenRead(src+"/mesh.bin"))){
   int n=r.ReadInt32(),f=r.ReadInt32(),s=r.ReadInt32();
   mesh.vertices=R3(r,n);mesh.normals=R3(r,n);mesh.uv=R2(r,n);mesh.subMeshCount=s;
   for(int i=0;i<s;i++){var a=new int[r.ReadInt32()];for(int j=0;j<a.Length;j++)a[j]=r.ReadInt32();mesh.SetTriangles(a,i,true);}
   if(r.BaseStream.Position!=r.BaseStream.Length)throw new Exception("Unread mesh bytes");
  }
  mesh.RecalculateTangents();mesh.RecalculateBounds();mesh.UploadMeshData(false);
  AssetDatabase.CreateAsset(mesh,gen+"/mesh_"+name+".asset");

  var stub=PVS22Builder.WriteStubShader(gen);
  var albedo=Import(src+"/albedo.png",TextureImporterType.Default,true);
  var spec=Import(src+"/spec.png",TextureImporterType.Default,false);
  var normal=Import(src+"/normal.png",TextureImporterType.NormalMap,false);
  var white=Flat(gen,"tex_white",Color.white,false);
  var bump=Flat(gen,"tex_flat_normal",new Color(.5f,.5f,1,1),true);
  // Submesh order matches prepare.py: body, glass. Names carry the role for finalize_clipons.py.
  var body=new Material(stub){name=name+"_body"};body.SetTexture("_MainTex",albedo);body.SetTexture("_SpecMap",spec);body.SetTexture("_BumpMap",normal);
  AssetDatabase.CreateAsset(body,gen+"/mat_body.asset");
  // Germanium for the thermal sight: dark grey with a purple-green sheen; the rest blue-violet night-vision glass.
  var glass=info.thermal
   ?PVS22Builder.LensMaterial(PVS22Builder.WriteLensShader(gen),name+"_glass",new Color(0.42f,0.30f,0.55f),new Color(0.35f,0.65f,0.40f),new Color(0.55f,0.50f,0.60f))
   :PVS22Builder.LensMaterial(PVS22Builder.WriteLensShader(gen),name+"_glass");
  AssetDatabase.CreateAsset(glass,gen+"/mat_glass.asset");

  var root=new GameObject(name);
  var lo=new Vector3(info.boundsMin[0],info.boundsMin[1],info.boundsMin[2]);var hi=new Vector3(info.boundsMax[0],info.boundsMax[1],info.boundsMax[2]);
  var pivot=root.AddComponent<PreviewPivot>();
  pivot.pivotPosition=(lo+hi)/2;pivot.pivotRotation=new Quaternion(0,0.7071068f,0,0.7071068f);pivot.scale=Vector3.one;
  pivot.Icon=new PreviewPivot.IconSettings{rotation=new Quaternion(0,0.8433914f,0,-0.5372996f),boundsScale=0.9f,perspective=15,orthographicSize=10};
  // Same node name pattern as the PVS-22, which ClipOnPlacement looks up.
  var lod=new GameObject("an_pvs22_LOD0");lod.transform.SetParent(root.transform,false);
  lod.AddComponent<MeshFilter>().sharedMesh=mesh;
  var mr=lod.AddComponent<MeshRenderer>();mr.sharedMaterials=new[]{body,glass};mr.shadowCastingMode=ShadowCastingMode.On;mr.receiveShadows=true;
  var box=lod.AddComponent<BoxCollider>();box.center=(lo+hi)/2;box.size=hi-lo;box.enabled=false;  // disabled like native mods
  // Markers for the client plugin: the two ends, the optical axis height, and the thermal flag.
  Marker(root,"pvs22_front",new Vector3(0,info.axisHeight,info.frontZ));
  Marker(root,"pvs22_rear",new Vector3(0,info.axisHeight,info.rearZ));
  Marker(root,"clipon_axis",new Vector3(0,info.axisHeight,0));
  if(info.thermal)Marker(root,"clipon_thermal",Vector3.zero);
  PVS22Builder.BuildSight(root,mesh,glass,gen,info.axisHeight,info.lensZ,info.lensRadius,info.thermal);
  string prefab=gen+"/"+name+".prefab";PrefabUtility.SaveAsPrefabAsset(root,prefab);UnityEngine.Object.DestroyImmediate(root);
  return new AssetBundleBuild{assetBundleName=BundleKey(key),assetNames=new[]{prefab}};
 }
 static void Marker(GameObject root,string n,Vector3 p){var m=new GameObject(n);m.transform.SetParent(root.transform,false);m.transform.localPosition=p;}
}
