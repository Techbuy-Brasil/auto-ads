import sys
from config_manager import adicionar, listar, obter, remover, atualizar
from ads_manager import AdManager, AdsError


def cmd_clientes(args):
    if args.action == "listar":
        data = listar()
        if data:
            print(f"{'ID':<20} {'Nome':<25} {'Conta'}:<20")
            print("-" * 65)
            for cid, info in data.items():
                print(f"{cid:<20} {info.get('nome', ''):<25} {info.get('ad_account_id', ''):<20}")
        else:
            print("Nenhum cliente.")
    elif args.action == "adicionar":
        adicionar(args.id, args.nome, args.ad_account_id, args.access_token)
    elif args.action == "remover":
        remover(args.id)


def cmd_campanhas(args):
    cliente = obter(args.client_id)
    if not cliente:
        print("Cliente não encontrado")
        sys.exit(1)
    mgr = AdManager(cliente["access_token"], cliente["ad_account_id"])

    if args.action == "listar":
        campanhas = mgr.listar_campanhas()
        for c in campanhas:
            print(f"{c['id']} | {c['name']} | {c.get('objective', '')} | {c['status']}")
    elif args.action == "criar":
        camp = mgr.criar_campanha(
            args.nome, args.objetivo, args.status, daily_budget=args.daily_budget
        )
        print(f"Campanha criada: {camp['id']} - {camp['name']}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AutoAds - Tráfego Pago")
    sub = parser.add_subparsers(dest="command", required=True)

    pc = sub.add_parser("clientes")
    pc.add_argument("action", choices=["listar", "adicionar", "remover"])
    pc.add_argument("--id", help="ID do cliente")
    pc.add_argument("--nome", help="Nome")
    pc.add_argument("--ad-account-id", help="act_123456")
    pc.add_argument("--access-token", help="Token")

    pca = sub.add_parser("campanhas")
    pca.add_argument("action", choices=["listar", "criar"])
    pca.add_argument("client_id", help="ID do cliente")
    pca.add_argument("--nome", help="Nome da campanha")
    pca.add_argument("--objetivo", default="VENDAS")
    pca.add_argument("--daily-budget", type=float, default=50)
    pca.add_argument("--status", default="PAUSED")

    args = parser.parse_args()
    if args.command == "clientes":
        cmd_clientes(args)
    elif args.command == "campanhas":
        cmd_campanhas(args)
