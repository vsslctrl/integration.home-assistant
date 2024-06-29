# VSSL
Home Assistant integration based on [vsslctrl](https://github.com/vsslctrl/vsslctrl) for controlling [VSSL's](https://www.vssl.com/) range of streaming amplifiers.

## Help
Looking for **A1** and **A.1x** testers, please get in touch if your interested in helping: <vsslcontrolled@proton.me>

Tested on:
 - **A.3x** software version **p15305.016.3701**
 - **A.6x** software version **p15305.017.3701**

## Important
There should not be any *[VSSL Agent's](https://vssl.gitbook.io/vssl-rest-api/getting-started/start)* running on the same network. If you dont know what this is, then you can ignore this notice.

## Installation

### Home Assistant Community Store (HACS)

If you dont have HACS installed, follow [documentation here](https://hacs.xyz/docs/setup/prerequisites)

1. Open HACS in Home Assistant
2. Select `Custom Repositories` using the 3 dots in top right
3. Add `https://github.com/vsslctrl/integration.home-assistant`
4. Select `Integration` as category
4. Search `VSSL` in `Repository Name`, download it and restart HA
5. Go to `settings` -> `Devices & Service` -> `Add Intigration` and search for `VSSL`
6. Follow prompts to add VSSL device

![VSSL Device](screenshot.png)

**...TODO**
- Discovery (vsslctrl already has function)
- More functions e.g EQ