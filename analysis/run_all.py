"""Regenerate every README figure: python analysis/run_all.py"""

import fig_best_response
import fig_curse
import fig_pnl
import fig_ruin
import fig_shading

for module in (fig_curse, fig_shading, fig_pnl, fig_ruin, fig_best_response):
    module.main()
