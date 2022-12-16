from meta_aggregation_api.providers.one_inch_v5 import OneInchProviderV5
from meta_aggregation_api.providers.paraswap_v5 import ParaSwapProviderV5
from meta_aggregation_api.providers.zerox_v1 import ZeroXProviderV1

all_providers = {
    ZeroXProviderV1.PROVIDER_NAME: ZeroXProviderV1,
    OneInchProviderV5.PROVIDER_NAME: OneInchProviderV5,
    ParaSwapProviderV5.PROVIDER_NAME: ParaSwapProviderV5,
}
