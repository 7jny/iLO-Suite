#!/usr/bin/env python3
"""
Build script for HP iLO 3 Standalone Remote Console JAR
Compiles all Java source files and packages them into console/bin/ilo3-console.jar
"""

import os
import sys
import glob
import shutil
import subprocess

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(base_dir, "src")
    bin_dir = os.path.join(base_dir, "bin")
    classes_dir = os.path.join(bin_dir, "classes")
    jar_file = os.path.join(bin_dir, "ilo3-console.jar")
    manifest_file = os.path.join(bin_dir, "MANIFEST.MF")

    print(f"[*] Base directory: {base_dir}")
    print(f"[*] Source directory: {src_dir}")

    # Ensure output directories exist
    os.makedirs(classes_dir, exist_ok=True)

    # Collect all .java files
    java_files = glob.glob(os.path.join(src_dir, "**", "*.java"), recursive=True)
    if not java_files:
        print("[!] No java files found in src directory!")
        sys.exit(1)

    print(f"[*] Found {len(java_files)} Java source files. Compiling...")

    # Compile with javac
    javac_cmd = ["javac", "-encoding", "UTF-8", "-d", classes_dir] + java_files
    res = subprocess.run(javac_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("[!] Javac compilation failed:")
        print(res.stderr)
        sys.exit(1)

    print("[+] Java compilation successful.")

    # Create Manifest
    with open(manifest_file, "w", encoding="utf-8") as f:
        f.write("Manifest-Version: 1.0\n")
        f.write("Main-Class: Main\n")
        f.write("Permissions: all-permissions\n")
        f.write("\n")

    p12_src = os.path.join(base_dir, "bridge.p12")
    if os.path.isfile(p12_src):
        shutil.copy(p12_src, os.path.join(classes_dir, "bridge.p12"))

    print("[*] Packaging JAR file...")
    # Package jar
    jar_cmd = ["jar", "cfm", jar_file, manifest_file, "-C", classes_dir, "."]
    res_jar = subprocess.run(jar_cmd, capture_output=True, text=True)
    if res_jar.returncode != 0:
        print("[!] JAR packaging failed:")
        print(res_jar.stderr)
        sys.exit(1)

    jar_size = os.path.getsize(jar_file)
    print(f"[+] Successfully built {jar_file} ({jar_size} bytes / {jar_size // 1024} KB)")

if __name__ == "__main__":
    main()
