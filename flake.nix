{
  description = "Development flake for khard";

  outputs = { self, nixpkgs }: {

    packages.x86_64-linux.default =
      nixpkgs.legacyPackages.x86_64-linux.khard.overridePythonAttrs (oa: rec {
        name = "khard-${version}";
        version = "${oa.version}post-dev+${if self ? shortRev then self.shortRev else "dirty"}";
        SETUPTOOLS_SCM_PRETEND_VERSION = version;
        postInstall = ''
          ${oa.postInstall}
          cp -r $src/khard/data $out/lib/python*/site-packages/khard
        '';
        src = ./.;
      });
    devShells.x86_64-linux.release =
      let pkgs = nixpkgs.legacyPackages.x86_64-linux; in
      pkgs.mkShell {
        packages = with pkgs; [
          git
          twine
          (python3.withPackages (p: with p; [
            build
            mypy
            pylint
            setuptools
            setuptools-scm
            wheel
          ] ++ self.packages.x86_64-linux.default.propagatedBuildInputs))
        ];
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
}
