#based on ComfyUI's and MinusZoneAI's fp8_linear optimization

import torch
import torch.nn as nn

def fp8_linear_forward(cls, original_dtype, input):
    weight_dtype = cls.weight.dtype
    if weight_dtype in [torch.float8_e4m3fn, torch.float8_e5m2]:
        tensor_2d = False
        if len(input.shape) == 2:
            tensor_2d = True
            input = input.unsqueeze(1)
        if len(input.shape) == 3:
            if weight_dtype == torch.float8_e4m3fn:
                inn = input.reshape(-1, input.shape[2]).to(torch.float8_e5m2)
            else:
                inn = input.reshape(-1, input.shape[2]).to(torch.float8_e4m3fn)
            w = cls.weight.t()

            scale_weight = torch.ones((1), device=input.device, dtype=torch.float32)
            scale_input = scale_weight

            bias = cls.bias.to(original_dtype) if cls.bias is not None else None
            out_dtype = original_dtype

            if bias is not None:
                o = torch._scaled_mm(inn, w, out_dtype=out_dtype, bias=bias, scale_a=scale_input, scale_b=scale_weight)
            else:
                o = torch._scaled_mm(inn, w, out_dtype=out_dtype, scale_a=scale_input, scale_b=scale_weight)

            if isinstance(o, tuple):
                o = o[0]

            if tensor_2d:
                return o.reshape(input.shape[0], -1)

            return o.reshape((-1, input.shape[1], cls.weight.shape[0]))
        else:
            cls.to(original_dtype)
            out = cls.original_forward(input.to(original_dtype))
            return out
    else:
        return cls.original_forward(input)

def convert_fp8_linear(module, original_dtype):
    setattr(module, "fp8_matmul_enabled", True)
    for name, module in module.named_modules():
        
        if isinstance(module, nn.Linear):
            if "blocks" in name:
                #print(module, name)
                original_forward = module.forward
                setattr(module, "original_forward", original_forward)
                setattr(module, "forward", lambda input, m=module: fp8_linear_forward(m, original_dtype, input))
