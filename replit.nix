{ pkgs }: {
  # Блок системных пакетов Replit/Nix.
  # Здесь перечислены зависимости, которые должны быть доступны в контейнерной среде.
  deps = [
    # python310 предоставляет интерпретатор для запуска Django-приложения.
    pkgs.python310

    # postgresql нужен для клиентских утилит и совместимости с PostgreSQL-стендом.
    pkgs.postgresql

    # openssl используется Python-библиотеками для TLS и криптографических операций.
    pkgs.openssl

    # zlib требуется некоторым Python-пакетам при установке и работе с архивами/изображениями.
    pkgs.zlib
  ];

  # Блок переменных окружения Nix.
  # LD_LIBRARY_PATH помогает Python-пакетам находить системные библиотеки во время запуска.
  env = {
    LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      pkgs.openssl
      pkgs.zlib
    ];
  };
}
