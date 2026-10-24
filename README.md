# KHUx-Native

The goal of this repo is a Kingdom Hearts Union χ executable that runs on its own: the game's rewritten code
built natively with the open-source libraries it uses, with no emulator, no lifted ARM code and no original
binary at run time.

The game code comes from [KHUx-Recomp](https://github.com/thethiny/KHUx-Recomp), included as the submodule
`recomp/`. Recomp holds the rewrite of all game functions and the verifier that checks each one against the
original. Fixes are made there and reach this repo by updating the submodule.

## Plan

1. A 32-bit build (clang, i686, Itanium C++ ABI, libc++). Pointer size and struct layout then match the
   original ARM32 build, so the rewrite's offsets hold as they are.
2. Named bindings, kept in recomp: every call the rewrite makes to the libraries by address gets a name. Recomp
   maps the names to its lifted code, this repo maps them to the real libraries.
3. The libraries built from their upstream sources (cocos2d-x, cocostudio, LWF and the others), switched in one
   at a time.
4. A standalone host: window, input, audio and files without the emulator.
5. Features: full screen, the bundled private server, 144 fps.

Later, the move to the native memory layout and 64-bit. From that point the rewrite is edited here and stops
matching the original 1:1.

## Getting the sources

```
git clone --recursive git@github.com:thethiny/KHUx-Native.git
```

or `git submodule update --init --recursive` in an existing clone.
