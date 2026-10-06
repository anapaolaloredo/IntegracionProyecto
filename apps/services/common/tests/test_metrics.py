from common import metrics


def test_inc_y_render_con_etiquetas():
    metrics.reiniciar()
    metrics.inc("cache_hits_total")
    metrics.inc("cache_hits_total")
    metrics.inc("jwt_rejected_total", motivo="revocado")
    texto = metrics.render("books")
    assert 'cache_hits_total{servicio="books"} 2' in texto
    assert 'jwt_rejected_total{motivo="revocado",servicio="books"} 1' in texto


def test_observar_genera_sum_y_count():
    metrics.reiniciar()
    metrics.observar("redis_latency_seconds", 0.5)
    metrics.observar("redis_latency_seconds", 1.5)
    texto = metrics.render("x")
    assert 'redis_latency_seconds_sum{servicio="x"} 2.0' in texto
    assert 'redis_latency_seconds_count{servicio="x"} 2' in texto


def test_etiquetas_no_pueden_romper_el_formato():
    metrics.reiniciar()
    metrics.inc("m", motivo='a"b\nc')
    assert 'm{motivo="ab c",servicio="s"} 1' in metrics.render("s")
