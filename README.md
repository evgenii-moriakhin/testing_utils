Этот код писался в рамках разных задач для упрощения юнит и интег. тестирования функционала приложения

backends папка содержит grpc/tcp/http сервера-стабы для локального запуска, конфигурируются они (grpc/http, tcp не пригодился)
через Правила, и согласно заданным правилам созданные сервера-заглушки отдают заранее заданный ответ

запускаю обычно через conftest.py, примеры таких стаб-бекендов с описанием ожидаемых входящих и исходящих ответов:

```python 
class BlaBlaBackend(HTTPBackend):
    port = 12345
    rules = [
        HTTPRule(
            query_params={
                "a": "1",
                "b": "asdasd",
            },
            result=HTTPResult(read_file(SOME_DIR / "blabla.xml")),
        ),
        ...
    ]
```

или 


```python 
class BlaBlaGRPCBackend(GRPCBackend):
    port = 10000

    rules = [
        GRPCRule(
            request_msg_cls=BlaBlaCls,
            grpc_method="blabla/blablamethod",
            message_args={"query": "tst"},
            output_handler=lambda req: BlaBlaResult(
                param1=True,
                param2="asda",
            ).SerializeToString(),
        ),
        ...
    ]
```


так же в данном репозитории парочка вспомогательных тестовых утилит: object_spier и ассерты, функционал их понятен наглядно на юнит-тестах
