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
    default = pkgs.callPackage khard {};
  in {
    packages.${system}.default = default;
    devShells.${system} = let
      upstream = p: default.nativeBuildInputs ++ default.propagatedBuildInputs;
      pythonEnv = pkgs.python3.withPackages (p:
        [
          p.build
          p.mypy
          p.pylint
        ]
        ++ (upstream p));
      packages = with pkgs; [git ruff pythonEnv];
    in {
      default = pkgs.mkShell {inherit packages;};
      release = pkgs.mkShell {
        packages = packages ++ [pkgs.twine];
        shellHook = ''
          cat <<EOF
          To publish a tag on pypi
          0. version=$(git tag --list --sort=version:refname v\* | sed -n '$s/^v//p')
          1. git checkout v\$version
          2. nix flake check
          3. python3 -m build
          4. twine check --strict dist/khard-\$version*
          5. twine upload -r khardtest dist/khard-\$version*
          6. twine upload -r khard dist/khard-\$version*
          EOF
        '';
      };
    };
    checks.${system} = let
      tests = default.override {doc = false;};
    in {
      inherit default;
      tests-python-311 = tests.override {python3 = pkgs.python311;};
      tests-python-312 = tests.override {python3 = pkgs.python312;};
      ruff = pkgs.runCommand "ruff" {} ''
        ${pkgs.ruff}/bin/ruff check ${./khard}
        touch $out
      '';
      mypy = pkgs.runCommand "mypy" {
        buildInputs = [
          (pkgs.python3.withPackages (p: [p.mypy] ++ default.propagatedBuildInputs))
        ];
      } "cd ${./.} && mypy && touch $out";
    };
  };
}
