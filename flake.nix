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
            version = "0.1.0";
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
        {
          options.programs.kitherd = {
            enable = lib.mkEnableOption "kitherd: Kitty + Herdr AI agent orchestration";
          };

          config = lib.mkIf config.programs.kitherd.enable {
            home.packages = with pkgs; [
              python3
              fzf
            ];

            xdg.configFile."kitty/herdr_panel.py".source =
              "${self}/skills/kitherd/scripts/herdr_panel.py";

            home.file.".agents/skills/kitherd".source = "${self}/skills/kitherd";
          };
        };

      homeManagerModule = self.homeManagerModules.default;
    };
}
