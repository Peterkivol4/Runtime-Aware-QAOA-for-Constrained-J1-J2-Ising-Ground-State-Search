# Research Journal

## 2026-03-01

I did not start this repo wanting to write a negative result. I wanted to know whether careful runtime handling could rescue small frustrated-spin QAOA experiments enough to make the comparison fair.

## 2026-03-10

The first routing-heavy runs were worse than I expected. The same source circuit came back with meaningfully different observable errors after transpilation, and the gap between “nice source diagram” and “actual executed object” stopped feeling cosmetic.

## 2026-03-27

One of the more annoying results was that a mitigation setting could improve the energy number while making correlation error worse. That was the point where I stopped thinking of runtime support as engineering polish and started treating trust rejection as a valid scientific output.

## 2026-04-18

I rewrote the repo voice into a dissent memo because the positive framing was hiding the real conclusion. The important thing here is not that the quantum path sometimes works a bit; it is that the decision boundary is fragile enough that I would not trust it over the fixed-sector classical baseline on these workloads.

## 2026-05-05

This repo now feels like the bridge between the others. It sits between the depth-resolution question from LayerField and the deformation-focused framing in FieldLine and TeleportDim, and it is the one that made me stop treating execution as “just implementation.”
