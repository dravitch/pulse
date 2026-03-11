{
  description = "PULSE - Personal Intelligence Operating System";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        pythonEnv = pkgs.python311.withPackages (ps: with ps; [
          fastapi
          uvicorn
          anthropic
          asyncpg
          feedparser
          pandas
          numpy
          httpx
          pydantic
          pydantic-settings
          apscheduler
          websockets
          python-dotenv
          ccxt
          aiohttp
          pytest
          pytest-asyncio
          pytest-cov
        ]);

      in {
        # Dev shell: nix develop
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.nodejs_20
            pkgs.nodePackages.npm
            pkgs.postgresql_15
            pkgs.timescaledb
            pkgs.nginx
            pkgs.git
          ];

          shellHook = ''
            echo "🚀 PULSE dev environment ready"
            echo ""
            echo "Commands:"
            echo "  createdb pulse              - Create database"
            echo "  psql -d pulse -f database/schema.sql  - Init schema"
            echo "  uvicorn backend.main:app --reload     - Start backend"
            echo "  cd frontend && npm run dev            - Start frontend"
            echo ""
            export PGDATA="$PWD/.pgdata"
            export PGHOST="localhost"
            export PGPORT="5432"
          '';
        };

        # App package: nix run
        packages.default = pkgs.writeShellApplication {
          name = "pulse";
          runtimeInputs = [ pythonEnv pkgs.nodejs_20 pkgs.postgresql_15 ];
          text = ''
            echo "Starting PULSE..."
            uvicorn backend.main:app --host 0.0.0.0 --port 8000
          '';
        };

        # NixOS module for deployment
        nixosModules.default = { config, lib, pkgs, ... }: {
          options.services.pulse = {
            enable = lib.mkEnableOption "PULSE Personal Intelligence OS";
            port = lib.mkOption {
              type = lib.types.port;
              default = 8000;
              description = "Backend API port";
            };
            dataDir = lib.mkOption {
              type = lib.types.str;
              default = "/var/lib/pulse";
              description = "Data directory";
            };
          };

          config = lib.mkIf config.services.pulse.enable {
            systemd.services.pulse-backend = {
              description = "PULSE Backend";
              after = [ "network.target" "postgresql.service" ];
              wantedBy = [ "multi-user.target" ];
              serviceConfig = {
                ExecStart = "${pythonEnv}/bin/uvicorn backend.main:app --host 0.0.0.0 --port ${toString config.services.pulse.port}";
                WorkingDirectory = config.services.pulse.dataDir;
                Restart = "always";
                User = "pulse";
              };
            };

            users.users.pulse = {
              isSystemUser = true;
              group = "pulse";
            };
            users.groups.pulse = {};

            services.nginx = {
              enable = true;
              virtualHosts."pulse.local" = {
                locations."/" = {
                  root = "${config.services.pulse.dataDir}/frontend/dist";
                  tryFiles = "$uri $uri/ /index.html";
                };
                locations."/api/" = {
                  proxyPass = "http://localhost:${toString config.services.pulse.port}";
                  proxyWebsockets = true;
                };
                locations."/ws" = {
                  proxyPass = "http://localhost:${toString config.services.pulse.port}";
                  proxyWebsockets = true;
                };
              };
            };
          };
        };
      }
    );
}
