#!/bin/sh
# Builds the server side of the four mods from PVS22Mod.cs: one assembly per clip-on (its own namespace, GUID and
# name, set by CLIPON_<KEY>), into bin/Release/<key>/.
cd "$(dirname "$0")"
DOTNET=D:/vssm-work/tools/dotnet/dotnet.exe
for key in pvs22 pvs27 pvs30 utc; do
  KEY=$(echo $key | tr a-z A-Z)
  "$DOTNET" build -c Release -nologo -v q -p:AssemblyName=UstAchae.ClipOnSight.$KEY -p:DefineConstants=CLIPON_$KEY \
    -p:IntermediateOutputPath=obj/$key/ -o bin/Release/$key || exit 1
done
