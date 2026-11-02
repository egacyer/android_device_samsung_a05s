# Experimental Samsung crypto HAL bring-up

This branch adds a **manual service startup test**, not working /data
decryption. `TW_INCLUDE_CRYPTO` and `TW_INCLUDE_CRYPTO_FBE` remain false.
Normal recovery startup does not start these new services. No new build has
been completed or flashed for this experiment yet.

The blobs in [crypto-blobs.json](crypto-blobs.json) were extracted unchanged
from SM-A057M firmware A057MUBSFDZE2 and its VNDK v33 APEX. The manifest records
each original path, destination and SHA-256. No captured logs, device identifiers,
credentials or encryption keys are included.

## What has been checked

The existing TWRP 12.1 linker successfully resolved the stock KeyMint and
Gatekeeper service dependencies on the running Android device using libraries
extracted from the previous TWRP image plus the firmware blobs. The loader was
invoked with `--list`; this does not run the HAL main functions or their library
constructors. All resolved library paths were in the isolated test directory.
This checks ELF loading, not Binder registration, TEE requests or decryption.

In addition to the stock vendor dependency chain, these seven VNDK v33 libraries
were needed:

- `android.hardware.security.keymint-V2-ndk.so`
- `android.hardware.security.secureclock-V1-ndk.so`
- `android.hardware.security.sharedsecret-V1-ndk.so`
- `android.system.suspend-V1-ndk.so`
- `libdmabufheap.so`
- `libhardware_legacy.so`
- `libion.so`

## Next hardware test

After building and booting this experimental image, from its ADB shell:

```sh
setprop a05s.crypto.test 1
sleep 3
getprop init.svc.a05s-keymint
getprop init.svc.a05s-gatekeeper
cat /tmp/a05s-crypto-test.log
service list | grep -iE 'keymint|sharedsecret|secureclock'
lshal | grep -i gatekeeper
a05s-diagnostics
```

The preparation script requires `ro.bootloader=A057MUBSFDZE2`. Before starting
the HALs, it sets and verifies Android version 15 and the actual system/vendor
patch level `2026-05-05`, obtained from the installed firmware's build.prop
files. It rejects other firmware and refuses an existing read/write EFS mount.
If needed, it mounts the existing EFS partition with `ro,noload` to prevent
journal replay. It does not import stock actions that create/chown key folders,
mount /data, or call `twrp decrypt`.

Retrieve `/tmp/a05s-diagnostics.tar.gz` using `adb pull`. Stop the test with:

```sh
setprop a05s.crypto.test 0
```

Running service processes alone do not prove the HALs registered successfully;
check the service listings and logcat too. Remaining work includes testing TEE
initialization in recovery, matching the framework service manifests to the
compiled userspace, and reviewing the metadata/FBE key handling before enabling
automatic decryption. This experiment has not established compatibility with
SM-A057F/G or other firmware versions.
