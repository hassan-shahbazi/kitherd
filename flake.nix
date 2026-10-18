{
  description = "Native AI Agent Orchestration in Kitty Terminal through Herdr";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs, ... }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = self.packages.${system}.kitherd;
          kitherd = pkgs.stdenv.mkDerivation {
            pname = "kitherd";
            version = "1.0.0";
            src = ./.;

            nativeBuildInputs = [ pkgs.makeWrapper ];
            buildInputs = [ pkgs.python3 ];

            installPhase = ''
              runHook preInstall
              mkdir -p $out/bin $out/share/kitherd/skills
              cp -r skills/kitherd $out/share/kitherd/skills/
              install -Dm755 skills/kitherd/scripts/herdr_panel.py $out/bin/herdr_panel.py
              wrapProgram $out/bin/herdr_panel.py \
                --prefix PATH : ${nixpkgs.lib.makeBinPath [ pkgs.python3 pkgs.fzf ]}
              runHook postInstall
            '';
          };
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              python3
              fzf
              gnumake
            ];
          };
        }
      );

      homeManagerModules.default =
        {
          config,
          lib,
          pkgs,
          ...
        }:
        let
          cfg = config.programs.kitherd;
        in
        {
          options.programs.kitherd = {
            enable = lib.mkEnableOption "kitherd: Kitty + Herdr AI agent orchestration";
          };

          config = lib.mkIf cfg.enable {
            home.packages = with pkgs; [
              python3
              fzf
              gnumake
            ];

            home.activation.kitherd = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
              export PATH="${
                lib.makeBinPath [
                  pkgs.gnumake
                  pkgs.coreutils
                  pkgs.git
                ]
              }:$PATH"

              SKILLS_CLI="skills"
              if ! command -v skills >/dev/null 2>&1; then
                if command -v bunx >/dev/null 2>&1; then
                  SKILLS_CLI="bunx skills"
                elif command -v npx >/dev/null 2>&1; then
                  SKILLS_CLI="npx skills"
                fi
              fi

              make -C "${self}" install \
                PREFIX="$HOME" \
                SKILLS_CLI="$SKILLS_CLI" \
                </dev/null || true
            '';
          };
        };

      homeManagerModule = self.homeManagerModules.default;
    };
}
