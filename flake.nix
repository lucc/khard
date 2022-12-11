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

  };
}
