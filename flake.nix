{
  description = "Development flake for khard";

  outputs = { self, nixpkgs }: {

    packages.x86_64-linux.default =
      nixpkgs.legacyPackages.x86_64-linux.khard.overrideAttrs (oa: rec {
        pname = "khard";
        name = "khard-${version}";
        version = "dev-${if self ? shortRev then self.shortRev else "dirty"}";
        SETUPTOOLS_SCM_PRETEND_VERSION = version;
        src = ./.;
      });
    devShells.x86_64-linux.release =
      let pkgs = nixpkgs.legacyPackages.x86_64-linux; in
      pkgs.mkShell {
        packages = with pkgs; [
          git
          twine
          (python3.withPackages (p: with p; [
            setuptools setuptools-scm wheel
          ]))
        ];
        shellHook = ''
        cat <<EOF
        To publish a tag on pypi
        0. version=...
        1. git checkout v$version
        2. python3 setup.py sdist bdist_wheel
        3. twine upload -r khardtest dist/khard-$version*
        4. twine upload -r khard dist/khard-$version*
        EOF
        '';
      };
  };
}
