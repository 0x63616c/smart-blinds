#include "smart_blinds/control.hpp"
#include <array>
#include <iostream>
int main() {
    std::array<blinds::Calibration, 3> blinds;
    const std::array<std::array<blinds::Knot, 3>, 3> points = {{
        {{{0, 0}, {600, 400}, {1000, 2400}}},
        {{{0, 200}, {700, 800}, {1200, 2500}}},
        {{{0, 100}, {900, 1000}, {1500, 2300}}}
    }};
    for (std::size_t i = 0; i < blinds.size(); ++i)
        if (!blinds[i].assign(points[i].data(), 3, 1)) return 1;
    const auto range = blinds::common_range(blinds.data(), blinds.size());
    if (!range) return 1;
    const auto height = blinds::group_height(*range, 50);
    std::cout << "Illustrative calibration, not measurements of the user's blinds.\n"
              << "Shared travel: " << range->low_mm << " to " << range->high_mm << " mm\n"
              << "Group 50% = bottom edge " << *height << " mm above the shared datum\n";
    for (std::size_t i = 0; i < blinds.size(); ++i)
        std::cout << "Blind " << i + 1 << ": encoder coordinate " << *blinds[i].count_at(*height) << '\n';
}
