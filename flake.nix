{
  description = "Development flake for khard";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = {
    self,
    nixpkgs,
  }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
    inherit (builtins) map head split replaceStrings mapAttrs;
    inherit (pkgs.lib) lists;
    pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
    clean = d: replaceStrings ["."] ["-"] (head (split "[^a-zA-Z0-9._-]" d));
    build = map clean pyproject.build-system.requires;
    deps = map clean pyproject.project.dependencies;
    opts = mapAttrs (name: map clean) pyproject.project.optional-dependencies;
    get = names: pkgs: map (name: pkgs.${name}) names;
    khard = {
      python3,
      doc ? true,
    }:
      python3.pkgs.buildPythonApplication {
        pname = "khard";
        version = "0.dev+${self.shortRev or self.dirtyShortRev}";
        pyproject = true;
        src = ./.;
        nativeBuildInputs = let
          names =
            build
            ++ lists.optionals doc opts.doc
            ++ lists.optional doc "sphinxHook";
        in
          get names python3.pkgs;
        sphinxBuilders = ["man"];
        propagatedBuildInputs = get deps python3.pkgs;
        postInstall = ''
          install -D misc/zsh/_khard $out/share/zsh/site-functions/_khard
          cp -r $src/khard/data $out/lib/python*/site-packages/khard
        '';
        # see https://github.com/scheibler/khard/issues/263
        preCheck = "export COLUMNS=80";
        pythonImportsCheck = ["khard"];
        checkPhase = "python3 -W error -m unittest -v";
      };
  in {
    packages.${system}.default = pkgs.callPackage khard {};
    devShells.${system} = let
      khard = self.packages.${system}.default;
      upstream = p: khard.nativeBuildInputs ++ khard.propagatedBuildInputs;
      pythonEnv = pkgs.python3.withPackages (p:
        [
          p.build
          p.mypy
          p.pylint
        ]
        ++ (upstream p));
    in {
      default = pkgs.mkShell {packages = with pkgs; [git pythonEnv];};
      release = pkgs.mkShell {
        packages = with pkgs; [git twine pythonEnv];
        shellHook = ''
          cat <<EOF
          To publish a tag on pypi
          0. version=$(git tag --list --sort=version:refname v\* | sed -n '$s/^v//p')
          1. git checkout v\$version
          2. python3 -m build
          3. twine check --strict dist/khard-\$version*
          4. twine upload -r khardtest dist/khard-\$version*
          5. twine upload -r khard dist/khard-\$version*
          EOF
        '';
      };
    };
    checks.${system} = {
      tests-python-311 = pkgs.callPackage khard {python3 = pkgs.python311;};
      tests-python-312 = pkgs.callPackage khard {python3 = pkgs.python312;};
    };
  };
}
