"""Fix lwjgl class paths for minecraft."""

# Program that fixes LWJGL java class path data for minecraft
# MIT License
# Copyright (c) 2022-2024 CoolCat467
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

# Helpful pre-launch command for Raspberry Pi OS:
# export MESA_GL_VERSION_OVERRIDE=4.2COMPAT

# Specify LWJGL path other than defined below in BASE_FOLDER:
# -Dorg.lwjgl.librarypath=<PATH>

# Useful debug arguments:
# -Dorg.lwjgl.util.DebugLoader=true -Dorg.lwjgl.util.Debug=true

__title__ = "Fix-LWJGL"
__author__ = "CoolCat467"
__version__ = "1.3.1-dev"
__license__ = "MIT"


import asyncio
import json
import os
import platform
import subprocess
import sys
from configparser import ConfigParser
from typing import Any, Final, Iterable, Iterator

import aiohttp

HOME = os.getenv("HOME", os.path.expanduser("~"))
XDG_DATA_HOME = os.getenv(
    "XDG_DATA_HOME",
    os.path.join(HOME, ".local", "share"),
)
XDG_CONFIG_HOME = os.getenv("XDG_CONFIG_HOME", os.path.join(HOME, ".config"))

FILE_TITLE = __title__.lower().replace("-", "_")
CONFIG_PATH = os.path.join(XDG_CONFIG_HOME, FILE_TITLE)
BASE_FOLDER = os.path.join(XDG_DATA_HOME, FILE_TITLE)
MAIN_CONFIG = os.path.join(CONFIG_PATH, f"{FILE_TITLE}_config.ini")
ALLOWED_TO_DOWNLOAD = True
TIMEOUT: int | None = None

OS = platform.system().lower()

OS_RENAME: Final = {"darwin": "macos"}
OS = OS_RENAME.get(OS, OS)

ARCH = platform.machine().lower()

ARCH_RENAME: Final = {
    "i386": "x86_64",
    "i686": "x86_64",
    "aarch64": "arm64",
    "aarch64_be": "arm64",
    "armv8b": "arm64",
    "armv8l": "arm64",
    "armv8": "arm64",
    "armhf": "arm32",
    "armv7b": "arm32",
    "armv7l": "arm32",
    "armv7": "arm32",
    "amd64": "x64",
    "amd32": "x32",
}

ARCH = ARCH_RENAME.get(ARCH, ARCH)

ARCH_IGNORE: Final = {"x86_64", "x32"}

# SO files in lwjgl build repository that don't start with
# "lwjgl_"
NOPRE_SO: Final = (
    "assimp",
    "bgfx",
    "glfw",
    "jemalloc",
    "openal",
    "opus",
    "shaderc",
    "spirv-cross",
    "moltenvk",
)

ARCH_PATH_RENAME: Final = {
    "linux/x86_64": "linux/x64",
    "macos/x86_64": "macosx/x64",
    "macos/arm64": "macosx/arm64",
}


def get_paths(jdict: dict[str, Any]) -> list[str]:
    """Read dictionary and figure out paths of files we want to update."""

    def read_dict(cdict: dict[str, Any]) -> list[str]:
        """Read a dictionary and return paths."""
        paths = []
        for path in cdict:
            nxt = cdict[path]
            # See next object.
            if isinstance(nxt, dict):
                # If dictionary, read and add our own path.
                add = read_dict(nxt)
                for file in add:
                    paths.append(os.path.join(path, file))
            else:
                # If it's a list or tuple, add all to our own paths joined.
                for file in nxt:
                    if isinstance(file, str):
                        paths.append(os.path.join(path, file))
        return paths

    return read_dict(jdict)


def get_address(user: str, repo: str, branch: str, path: str) -> str:
    """Get raw GitHub user content URL of a specific file."""
    return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}"


async def download_coroutine(
    session: aiohttp.ClientSession,
    url: str,
) -> bytes:
    """Return content bytes found at URL."""
    if not ALLOWED_TO_DOWNLOAD:
        log(
            f'Not allowed to download "{url}" because of configuration file',
            1,
        )
        sys.exit(1)

    # Go to the URL and get response
    try:
        async with session.get(url) as response:
            # Wait for our response
            data = await response.content.read()
            response.close()
    except asyncio.TimeoutError:
        log(f'Timeout Error while downloading from "{url}"', 1)
        raise
    return data


def log(msg: str, level: int = 0) -> None:
    """Log message."""
    lvl = ("INFO", "ERROR")[level]
    if level != 0:
        msg += "\a"
    print(f"[{__title__}/{lvl}]: {msg}")


def get_lwjgl_file_url(
    filepath: str,
    lwjgl_vers: str = "latest",
    branch: str = "release",
) -> str:
    """Return the URL of lwjgl file required."""
    return f"https://build.lwjgl.org/{branch}/{lwjgl_vers}/{filepath}"


class Module:
    """LWJGL Module class. Has filenames and file download paths."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        """Initialize module with name."""
        self.name = name

    def __repr__(self) -> str:
        """Return representation of self."""
        return f"{self.__class__.__name__}({self.name!r})"

    def __str__(self) -> str:
        """Return module name."""
        return self.name

    @property
    def system_library(self) -> str:
        """System library for this module."""
        pre = "lib"
        end = "so"
        if OS == "macos":
            end = "dylib"
        elif OS == "windows":
            pre = ""
            end = "dll"
        if "-" not in self.name:
            return f"{pre}{self.name}.{end}"
        base = self.name.split("-")[1]
        if base.lower() in NOPRE_SO:
            if OS == "windows" and base == "openal":  # Strange oddity
                base = "OpenAL"
            elif OS == "macos" and base == "moltenvk":
                base = "MoltenVK"
            return f"{pre}{base}.{end}"
        name = self.name.replace("-", "_")
        return f"{pre}{name}.{end}"

    @property
    def filenames(self) -> tuple[str, str]:
        """Tuple of module jar, module natives jar, and so file."""
        natives_vers = OS if ARCH in ARCH_IGNORE else f"{OS}-{ARCH}"
        return (
            f"{self.name}.jar",
            f"{self.name}-natives-{natives_vers}.jar",
            # self.system_library,
        )

    @property
    def file_paths(self) -> tuple[str, str]:
        """Tuple of lwjgl repository paths to module jar and natives."""
        natives_vers = OS if ARCH in ARCH_IGNORE else f"{OS}-{ARCH}"
        # arch_path = f'{OS}/{ARCH}'
        # arch_path = ARCH_PATH_RENAME.get(arch_path, arch_path)
        return (
            f"bin/{self.name}/{self.name}.jar",
            f"bin/{self.name}/{self.name}-natives-{natives_vers}.jar",
            # f'{arch_path}/{self.system_library}',
        )

    def __iter__(self) -> Iterator[str]:
        """Return iterator of self.filenames."""
        return iter(self.filenames)


def test_modules() -> None:
    """Test modules system."""
    names = (
        "lwjgl",
        "lwjgl-jemalloc",
        "lwjgl-openal",
        "lwjgl-opengl",
        "lwjgl-glfw",
        "lwjgl-stb",
        "lwjgl-tinyfd",
    )
    modules = list(map(Module, names))
    for module in modules:
        print("\n".join(module.file_paths))


async def download_file(
    session: aiohttp.ClientSession,
    url: str,
    folder: str,
) -> str:
    """Download files into given folder. Return file path saved to."""
    filename = url.split("/")[-1]
    filepath = os.path.join(folder, filename)
    if os.path.exists(filepath):
        return filepath
    data = await download_coroutine(session, url)
    if (
        b'<?xml version="1.0" encoding="UTF-8"?>\n<Error>' in data
        or b"404: Not Found" in data
    ):
        raise OSError(f'"{filename}" does not exist according to "{url}"!')
    # Could have aiofiles dependency and fix this, but I would rather not.
    with open(filepath, "wb") as sfile:  # noqa: ASYNC101  # sync `open`
        sfile.write(data)
    return filepath


async def download_files(
    session: aiohttp.ClientSession,
    urls: list[str],
    folder: str,
) -> list[str]:
    """Download multiple files from given URLs into a given folder."""
    coros = [download_file(session, url, folder) for url in urls]
    return await asyncio.gather(*coros)


async def download_lwjgl_files(
    session: aiohttp.ClientSession,
    urls: list[str],
    lwjgl_folder: str,
) -> None:
    """Download lwjgl files from URLs."""
    if not os.path.exists(lwjgl_folder):
        log(f'"{lwjgl_folder}" does not exist, creating it.')
        os.makedirs(lwjgl_folder)

    new_files = await download_files(session, urls, lwjgl_folder)
    log(f"{len(urls)} files downloaded.")

    # Make sure new files are executable
    for path in new_files:
        os.chmod(path, 0o755)  # noqa: S103  # We need executable privileges


async def download_lwjgl3_files(
    loop: asyncio.AbstractEventLoop,
    modules: Iterable[Module],
    lwjgl_folder: str,
    lwjgl_vers: str = "latest",
    branch: str = "release",
) -> None:
    """Download lwjgl 3 files given modules and lwjgl folder."""
    urls = []
    for module in modules:
        for file_path in module.file_paths:
            urls.append(get_lwjgl_file_url(file_path, lwjgl_vers, branch))

    client_timeout = aiohttp.ClientTimeout(TIMEOUT)

    # # Debug trace config
    # trace_config = aiohttp.TraceConfig()
    # for name in (
    #     n for n in dir(trace_config)
    #     if n.startswith('on_') and not 'dns' in n.split('_')
    # ):
    #     def make_me_log(name):
    #         log_name = ' '.join(x.title() for x in name.split('_')[1:])
    #         async def log_thing(session, trace_config_ctx, params):
    #             print('#'*32)
    #             print(log_name)
    #             print(f'\n{session = }\n')
    #             print(f'{trace_config_ctx = }\n')
    #             print(f'{params = }')
    #             print('#'*32+'\n')
    #         return log_thing
    #     getattr(trace_config, name).append(make_me_log(name))

    headers = {
        "User-Agent": f"python-fixlwjgl/{__version__}",
        "Accept": "binary/octet-stream, */*",
        "Accept-Encoding": "gzip, deflate",
    }

    # Make a session with our event loop
    async with aiohttp.ClientSession(
        loop=loop,
        headers=headers,
        # trace_configs=[trace_config],
        timeout=client_timeout,
    ) as session:
        await download_lwjgl_files(session, urls, lwjgl_folder)


async def rewrite_class_path_lwjgl3(
    loop: asyncio.AbstractEventLoop,
    class_path: list[str],
) -> list[str]:
    """Rewrite java class-path for lwjgl 3."""
    handled = set()

    new_lwjgl = os.path.join(BASE_FOLDER, f"lwjgl_3{ARCH}")
    specific_vers: tuple[int, ...] = (
        3,
        3,
        1,
    )  # assume 3.3.1, newest version as of 04/21/2022

    new_cls = []
    modules = []
    for elem in class_path:
        if "lwjgl" not in elem:
            new_cls.append(elem)
            continue

        name = elem.split(os.sep)

        idx = name.index("lwjgl")

        module_name = name[idx + 1]
        if module_name in handled:
            continue
        handled.add(module_name)

        vers_tuple = tuple(map(int, name[idx + 2].split(".")))
        assert (
            len(vers_tuple) == 3
        ), "Minecraft versions have exactly 2 decimal points!"
        if vers_tuple > specific_vers:
            specific_vers = vers_tuple

        modules.append(Module(module_name))

    download = set()
    for module in modules:
        for filename in module:
            file = os.path.join(new_lwjgl, filename)
            if not os.path.exists(file):
                download.add(module)
            new_cls.append(file)

    if download:
        to_get = tuple(download)
        names = ", ".join(map(str, to_get))
        vers = ".".join(map(str, specific_vers))
        log(
            "The following lwjgl modules were not found in "
            f'"{new_lwjgl}": {names}',
        )
        await download_lwjgl3_files(loop, to_get, new_lwjgl, vers, "release")

    return new_cls


async def download_lwjgl2_files(
    loop: asyncio.AbstractEventLoop,
    lwjgl_folder: str,
) -> None:
    """Download lwjgl 2 files from GitHub."""
    base = f"lwjgl2{ARCH}"
    lookup_file = f"{base}/files.json"
    listing_url = get_address(
        __author__,
        "fix-lwjgl",
        "HEAD",
        f"{lookup_file}",
    )

    client_timeout = aiohttp.ClientTimeout(TIMEOUT)
    # Make a session with our event loop
    async with aiohttp.ClientSession(
        loop=loop,
        timeout=client_timeout,
    ) as session:
        listing = await download_coroutine(session, listing_url)
        paths = get_paths(json.loads(listing))

        urls = [
            get_address(__author__, "fix-lwjgl", "HEAD", f"{base}/{p}")
            for p in paths
        ]

        await download_lwjgl_files(session, urls, lwjgl_folder)


async def rewrite_class_path_lwjgl2(
    loop: asyncio.AbstractEventLoop,
    class_path: list[str],
) -> list[str]:
    """Rewrite java class-path for lwjgl 2."""
    new_lwjgl = os.path.join(BASE_FOLDER, f"lwjgl_2{ARCH}")

    download = False
    if not os.path.exists(new_lwjgl):
        log(f'"{new_lwjgl}" does not exist!')
        download = True

    if download:
        if ARCH in {"arm64", "arm32"}:
            log("Downloading required files...")
            await download_lwjgl2_files(loop, new_lwjgl)
        else:
            log(f'Please create "{new_lwjgl}" or run with "-noop" flag', 1)
            sys.exit(1)

    # Keeping below for the time being, but
    # I think that simply adding LWJGL 2 library
    # path is good enough.

    # new_cls = []
    # find = set()
    # for elem in class_path:
    #     if not 'lwjgl' in elem:
    #         new_cls.append(elem)
    #         continue
    #     name = elem.split(os.sep)
    #     if 'paulscode' in name:
    #         new_cls.append(elem)
    #         continue
    #     module = 'lwjgl'
    #     if name.count('lwjgl') < 3:
    #         last = len(name) - 1 - tuple(reversed(name)).index('lwjgl')
    #         module = name[last+1]
    #     log(elem)
    #     find.add(f'{module}.jar')
    # log(find)
    # new_lwjgl = os.path.expanduser(f'{BASE_FOLDER}2{ARCH}')
    # for f in os.listdir(new_lwjgl):
    #     if f.endswith('.jar'):
    #         if f in find or f'-natives-{OS}-{arch}' in f:
    #             new_cls.append(os.path.join(new_lwjgl, f))
    #             log(f)
    # new_cls += [
    #     os.path.join(new_lwjgl, f) for f in os.listdir(new_lwjgl)
    #     if f.endswith('.jar')
    # ]
    # return new_cls
    return class_path


async def rewrite_mc_args(
    loop: asyncio.AbstractEventLoop,
    mc_args: list[str],
) -> list[str]:
    """Rewrite minecraft arguments."""
    global BASE_FOLDER  # pylint: disable=global-statement

    if "-cp" not in mc_args:
        return mc_args

    mc_vers = tuple(
        map(int, mc_args[mc_args.index("--version") + 1].split(".")),
    )
    lwjgl_vers = 2 if mc_vers < (1, 13) else 3
    # The snapshot minecraft updated to lwjgl 3 is apparently 17w43b
    # TODO: Handle snapshots properly

    lib_path = None
    for arg in mc_args:
        if arg.startswith("-Dorg.lwjgl.librarypath="):
            lib_path = arg.split("=", 1)[1]

    cls_path = mc_args.index("-cp")

    if lib_path is None:
        lib_path = os.path.expanduser(f"{BASE_FOLDER}{lwjgl_vers}{ARCH}")
        if lwjgl_vers == 2:
            log(
                "LWJGL library path is not supplied, setting it to "
                f'"{lib_path}"',
            )
            arg = f"-Dorg.lwjgl.librarypath={lib_path}"
            mc_args.insert(cls_path - 1, arg)
            cls_path += 1
    else:
        log(f'LWJGL library path is set to "{lib_path}"')
        BASE_FOLDER = os.path.expanduser(lib_path)

    class_path = mc_args[cls_path + 1].split(os.pathsep)

    if lwjgl_vers == 3:
        class_path = await rewrite_class_path_lwjgl3(loop, class_path)
    else:
        class_path = await rewrite_class_path_lwjgl2(loop, class_path)

    mc_args[cls_path + 1] = os.pathsep.join(class_path)

    mc_ver_text = ".".join(map(str, mc_vers))
    log(f"Rewrote lwjgl class paths for {mc_ver_text} (LWJGL {lwjgl_vers})")

    return mc_args


def launch_mc(mc_args: list[str]) -> int:
    """Launch minecraft with given arguments."""
    log("Launching minecraft from arguments...")
    # log(f'Launch Arguments: {" ".join(mc_args)}')
    # Can't easily check for untrusted input, and launchers have the same
    # issue, so not that big of a security risk. No permission changes,
    # and if someone is running this tool as root that's their problem, not
    # ours. We have absolutely no warranty for a reason.
    response = subprocess.run(mc_args, check=False)  # noqa: S603
    return response.returncode


def run(args: list[str]) -> int:
    """Fix LWJGL class-path and run minecraft."""
    global BASE_FOLDER, ALLOWED_TO_DOWNLOAD, TIMEOUT

    if not os.path.exists(CONFIG_PATH):
        log(f'Configuration path "{CONFIG_PATH}" does not exist, creating it.')
        os.makedirs(CONFIG_PATH)

    config = ConfigParser()
    config.read(MAIN_CONFIG)

    rewrite_config = False
    if config.has_section("main"):
        if config.has_option("main", "lwjgl_base_path"):
            base_path = config.get("main", "lwjgl_base_path")
            BASE_FOLDER = os.path.expanduser(base_path)
            log("Loaded lwjgl base path from config file.")
        else:
            rewrite_config = True
        if config.has_option("main", "can_download"):
            ALLOWED_TO_DOWNLOAD = config.getboolean("main", "can_download")
            log("Loaded if allowed to download from config file.")
        else:
            rewrite_config = True
        if config.has_option("main", "download_timeout"):
            value = config.get("main", "download_timeout")
            if value == "None":
                TIMEOUT = None
            else:
                TIMEOUT = config.getint("main", "download_timeout")
            log("Loaded download timeout from config file.")
        else:
            rewrite_config = True
    else:
        rewrite_config = True

    if not os.path.exists(MAIN_CONFIG):
        log("Config file does not exist.")
    elif rewrite_config:
        log("Config file is missing information.")
    else:
        log(f'Successfully read configuration file "{MAIN_CONFIG}".')

    if rewrite_config:
        log(f'Writing config file to "{MAIN_CONFIG}".')
        config.clear()
        config.read_dict(
            {
                "main": {
                    "lwjgl_base_path": os.path.expanduser(BASE_FOLDER),
                    "can_download": ALLOWED_TO_DOWNLOAD,
                    "download_timeout": str(TIMEOUT),
                },
            },
        )

        with open(MAIN_CONFIG, "w", encoding="utf-8") as file_point:
            config.write(file_point)

    if not args:
        log("No java arguments to rewrite lwjgl class paths for!")
        return 1

    first_arg = args[0].lower()

    if first_arg == "--install-for":
        arguments = args[1:]
        if not arguments:
            log("Missing argument(s) <mc-version> [<custom-install-path>]")
            return 1
        args = ["--version", arguments[0]]
        if len(arguments) >= 2 and arguments[1]:
            args.append(f"-Dorg.lwjgl.librarypath={arguments[1]}")
        lwjgl_vers = "3.3.1"
        files = (
            f"lwjgl/lwjgl/{lwjgl_vers}",
            f"lwjgl/lwjgl-jemalloc/{lwjgl_vers}",
            f"lwjgl/lwjgl-openal/{lwjgl_vers}",
            f"lwjgl/lwjgl-opengl/{lwjgl_vers}",
            f"lwjgl/lwjgl-glfw/{lwjgl_vers}",
            f"lwjgl/lwjgl-stb/{lwjgl_vers}",
            f"lwjgl/lwjgl-tinyfd/{lwjgl_vers}",
        )
        args.extend(("-cp", os.pathsep.join(files)))

    if first_arg == "-noop":
        mc_args = args[1:]
        log("Not performing any class path rewrites, -noop flag given.")
    else:
        loop = asyncio.new_event_loop()
        try:
            mc_args = loop.run_until_complete(rewrite_mc_args(loop, args))
        finally:
            loop.close()

    if first_arg == "--install-for":
        print_args = " ".join(map(str, mc_args))
        log(f"Rewritten arguments: `{print_args}`")
        return 0
    return launch_mc(mc_args)


def cli_run() -> None:
    """Command line run entry point."""
    log(f"{__title__} v{__version__} Programmed by {__author__}.")
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    cli_run()
