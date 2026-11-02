# USB and encrypted /data investigation

## USB changes pending hardware validation

The recovery USB init now:

- Uses `4e00000.ssusb` as the peripheral-mode fallback, matching the prebuilt
  command line and the controller observed on SM-A057M. An explicit
  `ro.boot.usb.dwc3_msm` value still takes precedence.
- Waits for both `sys.usb.ffs.ready=1` (ADB) and
  `sys.usb.ffs.mtp.ready=1` (MTP) before binding the combined gadget. The
  included TWRP MTP implementation sets the latter after writing descriptors.
- Removes the MTP function link when changing configurations, so ADB-only and
  fastbootd do not retain an inactive MTP function.
- Stops the actual `fastbootd` service in the legacy USB shutdown action.

These changes address init defects. They have not yet been tested on the
SM-A057F Bit 8 / One UI 6.1 configuration reported in upstream issue #2.
The prebuilt kernel already enables `CONFIG_USB_DWC3`, `CONFIG_USB_GADGET`,
`CONFIG_USB_F_FS`, and `CONFIG_USB_CONFIGFS_F_FS`.

Start ADB through init (`start adbd` from the recovery terminal), rather than
running another `adbd` process manually. Init provides its socket. The
`Failed to get adbd socket` message from a manually launched daemon does not
by itself identify a missing kernel driver.

## Collect logs even when /data cannot mount

In **Advanced > Terminal**, run:

```sh
a05s-diagnostics
```

The command writes only to `/tmp`; it does not attempt decryption, mount
partitions, or read encryption key files. Retrieve its archive from the PC:

```sh
adb pull /tmp/a05s-diagnostics.tar.gz
```

If USB is unavailable, use TWRP's file manager to copy the archive to external
storage that is already mounted. `/tmp` is RAM and is lost on reboot. If no
external storage is available, the generated `properties.txt` and `usb.txt`
can also be viewed in the terminal. Review logs before posting them publicly.

Test ADB on initial boot, MTP enable/disable followed by ADB, and **Reboot >
Fastboot**. From the PC, `fastboot devices` and `fastboot getvar is-userspace`
should identify fastbootd; use `fastboot reboot recovery` to return. Do not
flash or erase partitions for this connectivity test.

## Why encrypted /data is still unsupported

On the tested SM-A057M / One UI 7 device, Android mounts F2FS through a
`dm-default-key` mapping. The raw `userdata` partition is metadata-encrypted;
mounting it directly is expected to fail. This is separate from the USB
transport and is not evidence that userdata needs formatting.

The current device tree builds with `TW_INCLUDE_CRYPTO=false` and
`TW_INCLUDE_CRYPTO_FBE=false`. Therefore `twrp decrypt` cannot decrypt this
build. Setting `TW_INCLUDE_FBE_METADATA_DECRYPT=true` alone does not enable
the crypto code.

Stock uses `/vendor/bin/hw/android.hardware.security.keymint-service`,
Samsung's `mdfpp` Gatekeeper, and an AIDL KeyMint v2 manifest. The existing
Qualcomm helper starts HIDL Keymaster services and the matching stock
KeyMint/Gatekeeper executables and libraries are absent from the ramdisk.
Enabling the build flags alone does not supply those services or demonstrate
compatibility with Samsung's keys.

The active stock fstab on the tested UFS device is `fstab.default`. Its FBE
options are `aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized` and its key
directory is `/metadata/vold/metadata_encryption`. `fstab.emmc` has different
wrapped-key options; those must not be copied to the UFS configuration.

Remaining work before enabling decryption:

1. Check the stock KeyMint/Gatekeeper ELF dependency and symbol compatibility
   with the exact TWRP userspace, including libraries loaded at runtime.
2. Integrate the matching HAL services and their prerequisites without running
   stock initialization actions that create or modify encryption state.
3. Verify OS/security-patch properties against the installed firmware; the
   current placeholder patch level `2099-12-31` is not a validated crypto
   configuration.
4. Test metadata decryption and then credential-encrypted storage separately,
   preserving the existing encryption keys and files.

No working One UI 7 / Android 15 decryption result is claimed. The crypto flags,
fstab encryption options, prebuilt kernel, DTB, DTBO and driver blobs have not
been changed by the USB fixes. Formatting data or disabling encryption is not
part of this investigation.

References:

- [A05s USB report](https://github.com/TeamWin/android_device_samsung_a05s/issues/2)
- [A05s decryption report](https://github.com/TeamWin/android_device_samsung_a05s/issues/3)
- [Android metadata encryption](https://source.android.com/docs/security/features/encryption/metadata)
- [TWRP Qualcomm decryption prerequisites](https://github.com/TeamWin/android_device_qcom_twrp-common)
