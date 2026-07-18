# Runtime Resources

The runtime binaries in this directory are not stored in the repository.
Download them before running the project or building the EXE.

## Directory Structure

Prepare the directory as follows:

```text
resources/
├── README.md
├── clutch/
│   └── Clutch
└── libimobile/
    └── all files from the libimobiledevice package
```

## libimobiledevice for Windows

1. Create `resources/libimobile/`.
2. Download the Windows package from
   [L1ghtmann/libimobiledevice releases](https://github.com/L1ghtmann/libimobiledevice/releases).
3. Extract all files from the package directly into `resources/libimobile/`.

## Clutch

1. Create `resources/clutch/`.
2. Download `Clutch-2.0.4` from
   [KJCracks/Clutch releases](https://github.com/KJCracks/Clutch/releases).
3. Rename `Clutch-2.0.4` to `Clutch`.
4. Place it at `resources/clutch/Clutch`.

## Packaging

`pack_nuitka.py` copies this complete directory to `dist/resources/` after a
successful Nuitka build. Keep the generated `resources/` directory beside
`IPAClutchBatch.exe` when distributing or running the packaged application.
