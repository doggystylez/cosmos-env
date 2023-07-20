
from subprocess import run, DEVNULL
from argparse import ArgumentParser
from os.path import basename, isdir
from os import getcwd, uname
from time import sleep,time
from json import loads

lexec = ["lxc", "exec", "musl"]

def main():
    parser = ArgumentParser()
    parser.add_argument("pos_args", nargs="*", default=[], help="Positional arguments")
    parser.add_argument("-b", "--branch", metavar="VALUE", help="branch")
    parser.add_argument("-m", "--make", action="store_true", help="use make")
    args = parser.parse_args()
    positional_args = args.pos_args
    branch = args.branch
    make = args.make
    path = getcwd() if len(positional_args) < 1 else positional_args[0]
    bin_name = basename(path) if len(positional_args) < 2 else positional_args[1]
    if not isdir(f"{path}/cmd/{bin_name}"):
        print(f"main.go not found at {path}")
        return
    module = basename(path)
    if len(loads(run(["lxc", "list", "musl", "--format", "json"], capture_output=True).stdout)) > 0:
        print("starting go build environment")
    else:
        print("musl container doesn't exist - creating one")
        init_musl()
    run(["lxc", "start", "musl"], stderr=DEVNULL)
    run(["lxc", "file", "push", "-r", path, "musl/root/"], stdout=DEVNULL)
    if branch:
        if run(lexec + ["--cwd", f"/root/{module}", "--", "sh", "-c",
        f"git config --global --add safe.directory /root/{module} && git reset --hard && git checkout -q {branch}"], capture_output=True).returncode == 0:
            print(f"building from commit/tag {branch}")
        else:
            print(f"failed to checkout commit/tag {branch}")
            cleanup()
            return
    run(lexec + ["--cwd", f"/root/{module}", "--", "sh", "-c", f"rm {bin_name}"])
    go_mod = loads(run(lexec + ["--cwd", f"/root/{module}", "--", "sh", "-c", "go mod edit -json"], capture_output=True).stdout)
    go_version = f"go{go_mod['Go']}"
    wasmvm(go_mod)
    if go_version != run(lexec + ["--", "sh", "-c","go version | awk '{print $3}' | cut -d \".\" -f 1,2"], capture_output=True).stdout.strip().decode():
        PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        go_env = ["--env", f"GOROOT=/root/.gvm/{go_version}/go", "--env", f"PATH=/root/.gvm/{go_version}/go/bin:{PATH}"]
        if not run(lexec + ["--", "sh", "-c", f"ls /root/.gvm/{go_version}"], capture_output=True).stdout:
            gvm(go_version)
    else: go_env = None
    tidy = lexec + ["--cwd", f"/root/{module}", "--", "sh", "-c", "go mod tidy"]
    if go_env:
        tidy = tidy[:3] + go_env + tidy[3:]
    run(tidy, stderr=DEVNULL,stdout=DEVNULL)
    if make:
        print("using make")
        build = lexec + ["--env", "GOFLAGS=-buildvcs=false -o=.", "--cwd", f"/root/{module}", "--", "sh", "-c", "make build"]
    else:
        build = lexec + ["--cwd", f"/root/{module}", "--", "sh", "-c",
            f"go build -tags muslc -ldflags \"-w -s -linkmode=external -extldflags '-Wl,-z,muldefs -static'\" -buildvcs=false -trimpath ./cmd/{bin_name}"]
    if go_env:
        build = build[:3] + go_env + build[3:]
    start_time = time()
    run(build)
    end_time = time()
    if run(["lxc", "file", "pull", f"musl/root/{module}/{bin_name}", path], capture_output=True).returncode == 0:
        print(f"{bin_name} compiled at {path}/{bin_name} (build time {round(end_time - start_time, 3)} seconds)")
    else:
        print("compile failed")
    cleanup()

def init_musl():
    run(["lxc", "launch", "images:alpine/3.18", "musl"])
    sleep(2)
    run(lexec + ["--", "sh", "-c", "apk add --no-cache go gcc git curl make linux-headers"])
    run(["lxc", "stop", "musl"])

def cleanup():
    print("cleaning up")
    run(lexec + ["--", "sh", "-c", "rm -r /root/* && go clean -modcache"])
    run(["lxc", "stop", "musl"], stderr=DEVNULL)

def gvm(version):
    print(f"building {version}")
    run(lexec + ["--", "sh", "-c",
        f"mkdir -p /root/.gvm/{version} && apk add --virtual .go-deps openssl bash > /dev/null && "
            "curl -sL https://dl.google.com/go/{version}.src.tar.gz | tar -xzf - -C /root/.gvm/{version}"])
    run(lexec + ["--cwd", f"/root/.gvm/{version}/go/src", "--", "sh", "-c",
        "./make.bash > /dev/null && apk del .go-deps > /dev/null"])

def wasmvm(go_mod):
    wasm = None
    if go_mod["Replace"]:
       for replace in go_mod["Replace"]:
        if replace["Old"]["Path"] == "github.com/CosmWasm/wasmvm":
            wasm = replace["New"]["Version"]
    elif go_mod["Require"]:
       for require in go_mod["Require"]:
        if require["Path"] == "github.com/CosmWasm/wasmvm":
            wasm = require["Version"]
    if wasm:
        run(lexec + ["--", "sh", "-c",
            f"curl -sL https://github.com/CosmWasm/wasmvm/releases/download/{wasm}/libwasmvm_muslc.{uname().machine}.a -o /lib/libwasmvm_muslc.a"])
        checksum = run(lexec + ["--", "sh", "-c",
            "sha256sum /lib/libwasmvm_muslc.a"], capture_output=True, text=True).stdout.strip().split(" ")[0]
        checksums = run(lexec + ["--", "sh", "-c",
            f"curl -sL https://github.com/CosmWasm/wasmvm/releases/download/{wasm}/checksums.txt"], capture_output=True, text=True).stdout
        if checksum not in checksums:
            print("WARN: wasmvm checksum not verified")

if __name__ == "__main__":
    main()