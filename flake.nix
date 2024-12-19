{
  description = "Development flake for khard";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
  inputs.pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";
  outputs = {
    self,
    nixpkgs,
    pyproject-nix,
  }: let
    project = pyproject-nix.lib.project.loadPyproject {projectRoot = ./.;};
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
    khard = {
      python3,
      doc ? true,
    }: let
      attrs = project.renderers.buildPythonPackage {python = python3;};
      overrides = {
        version = "0.dev+${self.shortRev or self.dirtyShortRev}";
        build-system =
          attrs.build-system
          ++ [python3.pkgs.pytestCheckHook]
          ++ pkgs.lib.lists.optionals doc attrs.optional-dependencies.doc
          ++ pkgs.lib.lists.optional doc python3.pkgs.sphinxHook;
        sphinxBuilders = ["man"];
        postInstall = ''
          install -D -t $out/share/zsh/site-functions/ misc/zsh/_*
          cp -r $src/khard/data $out/lib/python*/site-packages/khard
        '';
        # see https://github.com/scheibler/khard/issues/263
        preCheck = "export COLUMNS=80";
        pythonImportsCheck = ["khard"];
        pytestFlagsArray = ["-s"];
      };
    in
      python3.pkgs.buildPythonApplication (attrs // overrides);
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
