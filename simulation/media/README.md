# Demo media

Put `.mp4` files here to use them as fake camera footage (looped forever):

```bash
# .env
FAKE_CAMERA03_SOURCE=file
FAKE_CAMERA03_VIDEO=/media/construction.mp4
```

The directory is mounted read-only at `/media` in the fake-camera containers. Video files are ignored
by git (see `.gitignore`); use footage you have the rights to.
