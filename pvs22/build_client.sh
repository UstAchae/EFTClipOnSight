#!/bin/sh
# Compiles the BepInEx plugin with the SDK's Roslyn against the game's own assemblies.
G=D:/games/SPT-4.1.6
mkdir -p package/client
refs=""
for f in "$G"/EscapeFromTarkov_Data/Managed/*.dll; do refs="$refs -r:$f"; done
D:/vssm-work/tools/dotnet/dotnet.exe D:/vssm-work/tools/dotnet/sdk/10.0.109/Roslyn/bincore/csc.dll -nologo -target:library -optimize+ -nostdlib+ -langversion:9 \
  -out:package/client/UstAchae.ClipOnSight.Client.dll $refs -r:$G/BepInEx/core/BepInEx.dll -r:$G/BepInEx/core/0Harmony.dll ClientSource/*.cs
