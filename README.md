# NeuroOps

**Head movement and facial gestures as game controls.** Built during USF Brain-Interface Club's BCI Build Sprint, with the original Modern Warfare 2 campaign's training course as the demo environment.

NeuroOps is a Windows prototype that translates webcam-based head orientation, facial expressions, and optional calibrated gaze into mouse and keyboard input. The repository also includes an experimental EMOTIV Cortex mental-command client. The working camera controller does not use the headset or EEG data.

## Team-reported experiment

The team reports combining exported EMOTIV INSIGHT 2 data with an OpenCV-based gesture controller to control MW2.

This describes the team's reported testing beyond the implementation included here. The export and pairing code are not included in this repository, so this workflow cannot currently be reproduced from this checkout. The available code paths are documented separately below.

## Quick start

Requirements: Windows, Python 3.12 with Tkinter, a webcam, and the original MW2 campaign for game output. Python 3.12 is the version tested during development.

```powershell
git clone https://github.com/BobTheBuilderIsOutdated/NeuroOps.git
cd NeuroOps
powershell -ExecutionPolicy Bypass -File setup-gestures.ps1
python webcam.py
```

The setup script installs dependencies into `.camera-deps` and downloads Google's Face Landmarker model into `models`. Dependencies and model binaries are not committed. After setup, `start-gestures.cmd` launches the controller.

1. Click **Start capture**, then **Calibrate neutral** and relax your face.
2. Keep **Look source** set to **Head**. Look straight ahead and click **Center head / F6**.
3. Enable **Mouse-look**, leave game output unchecked, and test in preview with **F8**.
4. Enable game output, focus MW2 campaign, and press **F8** again. **F9 stops output.**

See [the controls and calibration guide](CAMERA-QUICKSTART.md) for gaze mode, movement gestures, and troubleshooting.

## Controls

| Input | Action |
| --- | --- |
| Head yaw / pitch | Relative mouse-look; return to center to stop |
| Smile | One short fire press |
| Raised eyebrows | One reload press |
| Open mouth / purse lips | Optional forward / backward movement |
| Mouth shifted left / right | Optional strafe left / right |
| F6 | Center head and disarm |
| F8 | Arm / disarm |
| F9 | Stop and release generated input |

Gesture movement is optional; the normal mouse and keyboard remain available. Head mode requires only centering. Gaze mode offers five-point linear and nine-point quadratic calibration, with a circular dead zone and smoothing. It is experimental iris-position steering, not a validated eye tracker.

## How it works

```text
Webcam -> OpenCV -> MediaPipe face landmarks, expressions, and head transform
                    -> calibration + gesture gates + smoothing
                    -> foreground check -> Windows SendInput -> MW2 campaign
```

Inputs are restricted to the foreground `iw4sp.exe` process. Brief tracking failures pause output; fresh tracking and a neutral expression are required to resume. F9 and configuration changes disarm the controller. Frames are processed locally and are not recorded by this app. Calibration is kept in memory for the session.

## EMOTIV / Cortex prototype

`app.py` and `cortex.py` implement a separate experimental path: local Cortex WebSocket access, authorization, a loaded training profile, and the `com` mental-command stream. Launch it with `start.cmd` after running `setup.ps1`. It requires EMOTIV Launcher/Cortex, compatible hardware, a trained profile, and your own app credentials. Its simulation mode does not send game input.

This path was developed during the sprint, but reliable end-to-end EEG-driven gameplay was not established. Camera head/gesture control is the active implementation. The Cortex prototype subscribes to mental commands, not facial expressions; an EMOTIV `fac` integration is not implemented here.

Credentials can be entered locally. Optional `config.local.json` storage is plain text and excluded from Git; do not share it. Do not run both controllers simultaneously.

## Verification and limitations

```powershell
python -m unittest -v
```

The suite covers calibration math, gaze dead zones, head rotation, gesture gating, recovery from tracking loss, foreground restrictions, and input release. Tests run on Windows and require camera dependencies for numerical/GUI checks; they do not require live camera frames or send gameplay input.

The author reported successful MW2 input during the sprint. That is a local demonstration, not a performance benchmark. Accuracy, comfort, lighting tolerance, and game compatibility vary. Head or gaze motion controls turning velocity rather than exact aim. F9 depends on the application remaining responsive. This is a hackathon prototype, not a clinical accessibility product.

## Project files

- `webcam.py`: camera dashboard, capture worker, and control loop.
- `head_pose.py`, `gaze.py`, `gestures.py`, `gate.py`: tracking, calibration, and input decisions.
- `windows_input.py`: foreground-checked Windows inputs.
- `input_test.py`: user-triggered game-input diagnostic tool; close it before using F6 head centering.
- `app.py`, `cortex.py`: separate EMOTIV prototype and manually entered run log.
- `test_*.py`: regression tests.

## References

- [MediaPipe Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker)
- [OpenCV](https://opencv.org/)
- [EMOTIV Cortex API](https://emotiv.gitbook.io/cortex-api)
- [CheekyKeys](https://github.com/everythingishacked/CheekyKeys) and [Eye-Control-Mouse](https://github.com/rajiv2004-cloud/Eye-Control-Mouse) were reviewed as references; their source code was not incorporated.

Independent student project. Not affiliated with Activision, EMOTIV, Google, or the referenced projects. Third-party libraries and downloaded models retain their respective licenses.
