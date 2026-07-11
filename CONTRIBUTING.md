# Contribution guidelines

Contributing to this project should be as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features

## Github is used for everything

Github is used to host code, to track issues and feature requests, as well as accept pull requests.

Pull requests are the best way to propose changes to the codebase.

1. Fork the repo and create your branch from `main`.
2. If you've changed something, update the documentation.
3. Make sure your code lints (using `scripts/lint`).
4. Test you contribution.
5. Issue that pull request!

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be under the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report bugs using Github's [issues](../../issues)

GitHub issues are used to track public bugs.
Report a bug by [opening a new issue](../../issues/new/choose); it's that easy!

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

People *love* thorough bug reports. I'm not even kidding.

## Use a Consistent Coding Style

Use [Ruff](https://docs.astral.sh/ruff/) to make sure the code follows the style.

## Test your code modification

This custom component is based on [integration_blueprint template](https://github.com/ludeeus/integration_blueprint).

It comes with development environment in a container, easy to launch
if you use Visual Studio Code. With this container you will have a stand alone
Home Assistant instance running and already configured with the included
[`configuration.yaml`](./config/configuration.yaml)
file.

## Maintenance scripts

- `scripts/setup` - installs dev dependencies (`requirements.txt`).
- `scripts/develop` - launches a local Home Assistant instance (via the devcontainer) with this
  integration loaded from `custom_components/`, configured against `./config`.
- `scripts/lint` - runs `ruff format` and `ruff check --fix`.
- `scripts/generate_protobufs <run with no arguments>` - regenerates
  `custom_components/meshtastic/aiomeshtastic/protobuf/*_pb2.py(i)` from the `protobufs` git
  submodule. To bump to a newer Meshtastic protobuf schema:
  1. `cd protobufs && git fetch && git checkout <new tag> && cd ..`
  2. `pip install -r requirements.protobuf.txt`
  3. `./scripts/generate_protobufs`
  4. Check the "Protobuf Python Version: X.Y.Z" comment near the top of any regenerated
     `*_pb2.py` file, and make sure `custom_components/meshtastic/manifest.json`'s
     `protobuf>=X.Y.Z` requirement (and `requirements.txt`'s pin) is at least that version -
     otherwise Home Assistant can resolve an older `protobuf` package that fails to import
     the generated code at runtime.
  5. Commit the `protobufs` submodule bump together with the regenerated files (and the
     manifest bump from step 4, if any).
- `scripts/update_web_client <tag>` - updates the bundled Meshtastic web client
  (`custom_components/meshtastic/meshtastic_web/static`) from an official
  [meshtastic/web release](https://github.com/meshtastic/web/releases), independently of this
  addon's own release cycle - e.g. `./scripts/update_web_client v2.7.1`. It downloads the
  release's `build.tar` asset, decompresses it, patches `index.html` to work under the
  `/meshtastic/web/` sub-path this integration serves it from, and bumps
  `custom_components/meshtastic/meshtastic_web/version.py`. Review the diff and commit it
  yourself - the script never touches `manifest.json`/`hacs.json` or commits anything.

## License

By contributing, you agree that your contributions will be licensed under its MIT License.
