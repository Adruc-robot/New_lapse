# piAstro Configuration

## Overview

Capture behavior is configured per camera.

Each camera may define `capture_profiles` keyed by `scene_key`.

If no matching capture profile exists, the system captures a single image using
the exposure and gain calculated by the exposure controller.

Within a scene, profiles are evaluated in order. The first profile whose
conditions match is selected. A profile with no `conditions` acts as the
fallback for that scene.

## Example

{
  "imx462": {
    "capture_profiles": {
      "night": [
        {
          "settle_seconds": 0,
          "delay_between_images": 0,
          "measure_each_image": true,
          "awb": {
            "mode": "auto"
          },
          "sequence": {
            "repeat": 5,
            "steps": [
              {
                "label": "20s",
                "exposure_us": 20000000,
                "gain": 4.0
              },
              {
                "label": "5s",
                "exposure_us": 5000000,
                "gain": 4.0
              }
            ]
          }
        }
      ]
    }
  }
}

capture_profiles
    Object keyed by scene_key.

    Valid keys correspond to scenes produced by scene.py, such as:
        day
        golden_hour
        civil_twilight
        nautical_twilight
        astro_twilight
        night

    Each scene contains an ordered list of candidate capture profiles.

Profiles are evaluated from top to bottom.

A profile matches when all configured conditions are satisfied.

The first matching profile is selected.

A profile with no conditions matches all values and therefore acts as
the fallback for that scene.

conditions
    Optional.

    Restricts when a profile applies.

    Supported conditions:

        sun_altitude
        moon_altitude
        moon_illumination

    Each condition may specify:
        min
        max

    All specified conditions must match.

    "conditions": {
  "sun_altitude": {
    "min": 2.0,
    "max": 4.0
  },
  "moon_altitude": {
    "min": 0
  }
}

| Setting                | Type    | Default                | Meaning                                           |
| ---------------------- | ------- | ---------------------- | ------------------------------------------------- |
| `settle_seconds`       | integer | `0`                    | Time to allow camera/ISP to settle before capture |
| `delay_between_images` | integer | `0`                    | Delay between images in a multi-image sequence    |
| `measure_each_image`   | boolean | `false`                | Calculate image statistics for each final image   |
| `awb`                  | object  | implementation default | White-balance configuration                       |
| `sequence`             | object  | none                   | Defines multiple/repeated captures                |

"awb": {
  "mode": "auto"
}

or

"awb": {
  "mode": "manual",
  "gains": [1.5, 1.5]
}

sequence
    Optional.

    When omitted, one image is captured using the controller-calculated
    exposure and gain.

    repeat
        Integer.
        Number of times the complete steps list is executed.

    steps
        Ordered list of capture steps.

| Setting       | Type    | Required?   | Behavior                            |
| ------------- | ------- | ----------- | ----------------------------------- |
| `label`       | string  | recommended | Used in filenames/logging           |
| `exposure_us` | integer | no          | Overrides controller exposure       |
| `gain`        | decimal | no          | Overrides controller gain           |
| `awb`         | object  | no          | Overrides profile AWB for this step |


For each capture step:

exposure_us:
    step value if supplied
    otherwise controller-calculated exposure

gain:
    step value if supplied
    otherwise controller-calculated gain

awb:
    step-level AWB if supplied
    otherwise profile-level AWB
    otherwise normal camera/default behavior

{
  "label": "normal"
}


- Configuration is camera-specific.
- Python code should not contain camera-specific experimental behavior.
- Missing configuration means normal single-image behavior.
- Scene profiles should only be added when special behavior is needed.
- Sequence duration should remain shorter than the scheduler interval.
- Conditional profiles should be ordered from most specific to least specific.
- An unconditional profile should appear last when used as a fallback.