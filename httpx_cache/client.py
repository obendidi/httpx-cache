import typing as tp

import httpx
from httpx._config import (
    DEFAULT_LIMITS,
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_TIMEOUT_CONFIG,
    Limits,
    Proxy,
)
from httpx._types import (
    AuthTypes,
    CertTypes,
    CookieTypes,
    HeaderTypes,
    ProxiesTypes,
    QueryParamTypes,
    TimeoutTypes,
    URLTypes,
    VerifyTypes,
)

from httpx_cache.cache import BaseCache, DictCache
from httpx_cache.transport import AsyncCacheControlTransport, CacheControlTransport


class Client(httpx.Client):
    def __init__(
        self,
        *,
        auth: AuthTypes = None,
        params: QueryParamTypes = None,
        headers: HeaderTypes = None,
        cookies: CookieTypes = None,
        verify: VerifyTypes = True,
        cert: CertTypes = None,
        http1: bool = True,
        http2: bool = False,
        proxies: ProxiesTypes = None,
        mounts: tp.Mapping[str, httpx.BaseTransport] = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
        follow_redirects: bool = False,
        limits: Limits = DEFAULT_LIMITS,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        event_hooks: tp.Mapping[str, tp.List[tp.Callable]] = None,
        base_url: URLTypes = "",
        transport: httpx.BaseTransport = None,
        app: tp.Callable = None,
        trust_env: bool = True,
        cache: tp.Optional[BaseCache] = None,
        cacheable_methods: tp.Tuple[str, ...] = ("GET",),
        cacheable_status_codes: tp.Tuple[int, ...] = (200, 203, 300, 301, 308),
        always_cache: bool = False,
    ):
        self.cache = cache or DictCache()
        self.cacheable_methods = cacheable_methods
        self.cacheable_status_codes = cacheable_status_codes
        self.always_cache = always_cache
        super().__init__(
            auth=auth,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            follow_redirects=follow_redirects,
            max_redirects=max_redirects,
            event_hooks=event_hooks,
            base_url=base_url,
            trust_env=trust_env,
            verify=verify,
            cert=cert,
            http1=http1,
            http2=http2,
            proxies=proxies,
            mounts=mounts,
            limits=limits,
            transport=transport,
            app=app,
        )

    def _init_transport(
        self,
        verify: VerifyTypes = True,
        cert: CertTypes = None,
        http1: bool = True,
        http2: bool = False,
        limits: Limits = DEFAULT_LIMITS,
        transport: httpx.BaseTransport = None,
        app: tp.Callable = None,
        trust_env: bool = True,
    ) -> CacheControlTransport:
        _transport = super()._init_transport(
            verify=verify,
            cert=cert,
            http1=http1,
            http2=http2,
            limits=limits,
            transport=transport,
            app=app,
            trust_env=trust_env,
        )
        if isinstance(_transport, CacheControlTransport):
            return _transport
        return CacheControlTransport(
            transport=_transport,
            cache=self.cache,
            cacheable_status_codes=self.cacheable_status_codes,
            cacheable_methods=self.cacheable_methods,
            always_cache=self.always_cache,
        )

    def _init_proxy_transport(
        self,
        proxy: Proxy,
        verify: VerifyTypes = True,
        cert: CertTypes = None,
        http1: bool = True,
        http2: bool = False,
        limits: Limits = DEFAULT_LIMITS,
        trust_env: bool = True,
    ) -> CacheControlTransport:
        return CacheControlTransport(
            transport=super()._init_proxy_transport(
                verify=verify,
                cert=cert,
                http1=http1,
                http2=http2,
                limits=limits,
                trust_env=trust_env,
                proxy=proxy,
            ),
            cache=self.cache,
            cacheable_status_codes=self.cacheable_status_codes,
            cacheable_methods=self.cacheable_methods,
            always_cache=self.always_cache,
        )


class AsyncClient(httpx.AsyncClient):
    def __init__(
        self,
        *,
        auth: AuthTypes = None,
        params: QueryParamTypes = None,
        headers: HeaderTypes = None,
        cookies: CookieTypes = None,
        verify: VerifyTypes = True,
        cert: CertTypes = None,
        http1: bool = True,
        http2: bool = False,
        proxies: ProxiesTypes = None,
        mounts: tp.Mapping[str, httpx.AsyncBaseTransport] = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
        follow_redirects: bool = False,
        limits: Limits = DEFAULT_LIMITS,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        event_hooks: tp.Mapping[str, tp.List[tp.Callable]] = None,
        base_url: URLTypes = "",
        transport: httpx.AsyncBaseTransport = None,
        app: tp.Callable = None,
        trust_env: bool = True,
        cache: tp.Optional[BaseCache] = None,
        cacheable_methods: tp.Tuple[str, ...] = ("GET",),
        cacheable_status_codes: tp.Tuple[int, ...] = (200, 203, 300, 301, 308),
        always_cache: bool = False,
    ):
        self.cache = cache or DictCache()
        self.cacheable_methods = cacheable_methods
        self.cacheable_status_codes = cacheable_status_codes
        self.always_cache = always_cache
        super().__init__(
            auth=auth,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            follow_redirects=follow_redirects,
            max_redirects=max_redirects,
            event_hooks=event_hooks,
            base_url=base_url,
            trust_env=trust_env,
            verify=verify,
            cert=cert,
            http1=http1,
            http2=http2,
            proxies=proxies,
            mounts=mounts,
            limits=limits,
            transport=transport,
            app=app,
        )

    def _init_transport(
        self,
        verify: VerifyTypes = True,
        cert: CertTypes = None,
        http1: bool = True,
        http2: bool = False,
        limits: Limits = DEFAULT_LIMITS,
        transport: httpx.AsyncBaseTransport = None,
        app: tp.Callable = None,
        trust_env: bool = True,
    ) -> AsyncCacheControlTransport:
        _transport = super()._init_transport(
            verify=verify,
            cert=cert,
            http1=http1,
            http2=http2,
            limits=limits,
            transport=transport,
            app=app,
            trust_env=trust_env,
        )
        if isinstance(_transport, AsyncCacheControlTransport):
            return _transport
        return AsyncCacheControlTransport(
            transport=_transport,
            cache=self.cache,
            cacheable_status_codes=self.cacheable_status_codes,
            cacheable_methods=self.cacheable_methods,
            always_cache=self.always_cache,
        )

    def _init_proxy_transport(
        self,
        proxy: Proxy,
        verify: VerifyTypes = True,
        cert: CertTypes = None,
        http1: bool = True,
        http2: bool = False,
        limits: Limits = DEFAULT_LIMITS,
        trust_env: bool = True,
    ) -> AsyncCacheControlTransport:
        return AsyncCacheControlTransport(
            transport=super()._init_proxy_transport(
                verify=verify,
                cert=cert,
                http1=http1,
                http2=http2,
                limits=limits,
                trust_env=trust_env,
                proxy=proxy,
            ),
            cache=self.cache,
            cacheable_status_codes=self.cacheable_status_codes,
            cacheable_methods=self.cacheable_methods,
            always_cache=self.always_cache,
        )
