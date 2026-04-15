# Flake for polysh, only used for easier development and testing on nix-based systems.
# Might be used to build and test the package on multiple platforms, but is not intended/supported for production use.
{
  description = "Remote shell multiplexer for executing commands on multiple hosts";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          polysh = pkgs.python3Packages.buildPythonApplication {
            pname = "polysh";
            version = "0.15";

            pyproject = true;

            build-system = with pkgs.python3Packages; [
              hatchling
            ];

            src = ./.;

            meta = with pkgs.lib; {
              description = "Remote shell multiplexer for executing commands on multiple hosts";
              homepage = "https://github.com/innogames/polysh";
              license = licenses.gpl2Plus;
              maintainers = with maintainers; [ seqizz ];
              platforms = platforms.unix;
            };
          };

          default = self.packages.${system}.polysh;
        }
      );

      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              python3
              python3Packages.hatchling
            ];
          };
        }
      );
    };
}
