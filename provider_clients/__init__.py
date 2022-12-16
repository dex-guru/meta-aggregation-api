from meta_aggregation_api.providers import (ZeroXProviderV1, OneInchProviderV5,
                                            ParaSwapProviderV5)

all_providers = {
    ZeroXProviderV1.PROVIDER_NAME: ZeroXProviderV1,
    OneInchProviderV5.PROVIDER_NAME: OneInchProviderV5,
    ParaSwapProviderV5.PROVIDER_NAME: ParaSwapProviderV5,
}
