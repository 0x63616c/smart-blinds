# STUSB4500 factory profile and offline checks

The proposed port accepts **9 V/2.5 A or 15 V/2.5 A**, with a 5 V/1.5 A fallback that must leave the application power path blocked. Factory NVM must set `POWER_ONLY_ABOVE_5V=1` and `REQ_SRC_CURRENT=0`. The C6 does not share this I2C bus, so these settings must work autonomously after reset, including with an absent or depleted pack.

The offline tool implements the documented PDO fields and the `POWER_ONLY_ABOVE_5V` mapping independently traced through ST's GUI serializer and inverse decoder. It preserves unspecified baseline bits, compares every NVM byte and checks an active PDO-register capture. It **cannot yet produce an approved programming image**: discharge timing, baseline/silicon review and hardware acceptance remain unqualified. Every generated proposal is marked `INCOMPLETE_DO_NOT_PROGRAM`; successful readback never changes that status. There is no hardware backend, erase/program command, flashing CLI or owner-device access.

## Source evidence

- [ST's NVM flasher](https://github.com/usb-c/STUSB4500/blob/55d1109e7ef0cffc2ffef2494095d23306594601/NVM_Flasher/Src/NVM/USBPD_CUST_NVM_API.c), pinned to commit `55d1109e7ef0cffc2ffef2494095d23306594601`, supplies the actual 5 × 8-byte sector read/erase/program sequence. Its source SHA-256 is `57d883e2840a8f825c42fcae550109cfe326e890b3facac67ac1a953b4edd1ab`.
- ST's **39-page “STUSB4500 NVM registers — Description and generic access”** is attached by ST technical moderator Didier Herrouin in [this manufacturer discussion](https://community.st.com/others-hardware-and-software-57/stusb4500-clarification-on-vbus-discharge-default-configuration-and-nvm-address-details-157984). The retrieved PDF SHA-256 is `a1f35ffea672cef0a32bbd818dd7f5795cfe4bd641960bbf70a5b2374a3927e4`. Pages 22 and 25–28 supply the field locations used here. It has conflicting reserved-byte defaults in its detailed tables versus page 19; the generator therefore preserves the supplied baseline instead of manufacturing reserved bytes.
- [UM2650 Rev 2](https://github.com/usb-c/STUSB4500/blob/55d1109e7ef0cffc2ffef2494095d23306594601/Doc/User_manuals/um2650-the-stusb4500-software-programing-guide-stmicroelectronics_v2.pdf), sections 3.60–72, supplies the active PDO count and byte addresses. SHA-256: `585c084b50fdb2075745d8904ae95f18a731ff50d02a328c3417d7f4e0bc2652`.
- The [ST datasheet](https://www.st.com/resource/en/datasheet/stusb4500.pdf), sections 2.2.10, 3.3, 3.4.2 and 5, defines the required gate behavior, current lookup and discharge coefficients. The current circuit records DS12499 Rev 8; field semantics were also checked against the available Rev 7 text. These sources do not replace testing the selected silicon.

The NVM note calls `E6[3:0]` reserved. The [hash-bound manufacturer GUI audit](stusb4500-gui-evidence.md) now supplies the missing field evidence: its named checkbox maps to `E6[3]` in both the forward serializer and inverse decoder. The exact GUI 1.08 artifact was statically inspected without execution. The mapping is an inference from that primary binary, not a hardware test or a claim that the old note documents the field. Exhaustive forward/inverse and isolated-bit checks accompany it; actual contract/gate acceptance remains required.

## Documented proposal

NVM addresses `C0..E7` below are **image offsets**, not directly accessible I2C registers. NVM access goes through buffer `53` and controls `95..97`.

| Field | NVM location | Proposed setting |
|---|---|---|
| PDO count | `DA[2:1]` | 3 |
| PDO1 current | `DA[7:4]` | Lookup 5: 1.5 A; voltage fixed at 5 V |
| PDO2 current | `DC[3:0]` | Lookup 9: 2.5 A |
| PDO3 current | `DD[7:4]` | Lookup 9: 2.5 A |
| PDO2 voltage | `E0[7:6]`, `E1[7:0]` | 180 × 50 mV = 9 V |
| PDO3 voltage | `E2[7:0]`, `E3[1:0]` | 300 × 50 mV = 15 V |
| USB data capability | `DA[0]` | 1; D+/D− route to C6 native USB |
| Unconstrained power | `DA[3]` | 0 |
| Request source current | `E6[4]` | 0; request the configured sink current |
| Disable automatic discharge | `C9[5]` | 0; automatic discharge remains enabled |
| Discharge to 0 V / lower PDO | `CA[7:4]` / `CA[3:0]` | Preserve baseline unless explicitly proposed; neither choice is qualified |
| Power only above 5 V | `E6[3]`, static ST GUI evidence | 1; mapped and patched, hardware behavior untested |

Voltage-monitor shifts, unused flexible current, GPIO/POWER_OK configuration and reserved bits remain unchanged. Their preservation does not establish that an arbitrary baseline is correct. The reference fixture is explicitly the note's page-19 example, **not a read from a physical device**. Full baseline review and controlled GUI comparison are required before adopting any image.

The nominal coefficients are 84 ms per step to 0 V and 24 ms per step to a lower PDO in the datasheet. The default 9/12 values imply 756/288 ms nominal settings, not guaranteed discharge of this board. The circuit's two 3 kΩ resistor chains, effective capacitors, charger reverse paths, residual pack/system energy and power glitches must be measured. Changing a coefficient does not qualify compliance or repair an unknown discharge path.

## Offline use

Only Python's standard library is needed. Input is ST's five-row text format with eight bytes per row, starting at C0/C8/D0/D8/E0. Missing, duplicate, out-of-range and malformed rows are rejected. Comments may start with `#` or `//`.

```sh
python3 firmware/tools/stusb4500.py propose \
  firmware/tools/fixtures/stusb4500-reference-baseline.txt > work/stusb4500-proposal.json
python3 firmware/tools/stusb4500.py read-plan > work/stusb4500-read-plan.json
python3 firmware/tools/stusb4500.py compare \
  work/stusb4500-proposal.json work/fixture-nvm-readback.txt
python3 firmware/tools/stusb4500.py compare-runtime \
  work/stusb4500-proposal.json work/fixture-runtime.json
python3 -m unittest discover -s firmware/tools -p 'test_stusb4500.py' -v
```

Optional `--to-zero 1..15` / `--to-lower-pdo 1..15` make explicit timer proposals, retaining the blocked status. There is intentionally no C-header or ready-to-flash export. Proposal schema v2 includes the GUI evidence hash and above-5 V bit; regenerate older v1 offline proposals. Validation recomputes the entire record from its baseline and overrides; changing the candidate, hash, evidence, approval flags or unresolved list is rejected.

An offline active-register capture has this structure:

```json
{
  "schema": "smart-blinds/stusb4500-runtime/v1",
  "device_id": 33,
  "pdo_count_register": 3,
  "pdo_registers_hex": "96900104fad00200fab00400"
}
```

The example is synthetic. `device_id` comes from register `2F` (the pinned ST firmware lists `21`/`25` hex), count from `70`, and the 12 bytes from `85..90` are three **little-endian** PDOs. The comparison checks supply type, voltage/current, and PDO1 communication/unconstrained-power flags. It does not claim every protocol flag matches, prove a physical reset from a file, measure the gate, or treat local sink PDOs as the negotiated source RDO. Mismatches return exit status 1; malformed input returns 2.

## Future fixture procedure

This is a fixture implementation specification, not an instruction to program the current proposal. No fixture exists or has been exercised. The following gates must be completed before an approved image is written:

1. Qualify timer choices, review all preserved baseline bits against the actual silicon, and retain the static field audit plus a controlled ST GUI/version comparison and final image digest. The current tool cannot release the hardware gates.
2. Use a reviewed fixture with a common ground, a 3.3 V I2C pull-up supply and address **0x28**. The fixture bus is isolated from the C6. USB supplies ST VDD; the fixture must not feed the chip's internal regulator outputs or energize an unpowered bus. The controller capture presently reserves factory I2C/reset interfaces; actual pogo pads and mechanical access remain a layout task.
3. Keep cells, motor and charger enable isolated/inhibited using fixture hardware. A default or partly programmed chip cannot be trusted to enforce the final gate policy. Start from a controlled 5 V source, verify voltage/current and independent output isolation, then record board serial, silicon ID and a complete original NVM read before any destructive operation.
4. Implement the manufacturer's sequence with explicit ACK/short-read handling, finite per-transfer deadlines, bounded polling, an overall deadline and cleanup. The tool's **read plan** supplies proposed 10 ms transfer, 100 ms request-poll and 1 s overall software budgets. These are conservative fixture abort policies, not measured silicon timing guarantees. Reading NVM writes its control registers; it is not an ordinary passive register dump.
5. After an approved one-time programming operation, exit test mode, read all five sectors again and compare all 40 bytes. Any mismatch, timeout or power interruption makes the unit unqualified; do not automatically keep erasing/retrying. Retain the original and failed readbacks and require controlled recovery.
6. Reset/re-power with fixture logging and read active PDO registers again. Only then perform the electrical acceptance matrix: 5 V/no PD and insufficient-current sources remain blocked; both accepted 9 V and 15 V contracts work; detach, hard reset, voltage changes, rapid power interruption, reverse power and short faults behave as designed. Observe raw VBUS, downstream VBUS and the enable/gate signals, including both discharge paths. A matching NVM dump alone does not pass these tests.
7. Record immutable factory image/readback digests, firmware/circuit revision, fixture version and measured results against the unit serial. The C6's future `factory_image_verified` evidence must come from this controlled process; the offline proposal must never set it.

### Exact manufacturer programming sequence to port later

The pinned `NVM_Flasher` implementation is authoritative for this proposed port. Its comments contain obsolete `9E/9F` addresses and an incorrect erase-byte comment; the actual definitions and executable operations use `95/96/97` and the computed values below. The note also contains a buffer-address typo. Do not turn those comments into a different transaction sequence.

- Enter: write `95=47`, `53=00`, `96=00`, then `96=C0`.
- Select all five erase sectors: write `97=FA` (`1F << 3 | WRITE_SER(2)`), then `96=D0`; poll `96[4]` until clear with a deadline.
- Soft-program preparation: write `97=07`, then `96=D0`; poll. Erase: write `97=05`, then `96=D0`; poll.
- For each sector 0..4: write its **eight bytes to buffer 53**; write `96=C0`, `97=01`, `96=D0`; poll. Then write `97=06`, `96=D0|sector`; poll.
- Exit: write two bytes `40 00` starting at `96`, then write `95=00`. Attempt bounded cleanup after errors too, without treating cleanup as successful programming or retrying erase automatically.
- Readback: the offline `read-plan` follows the source's enter/read-sector/exit operations with read opcode zero. No erase/program opcodes appear in that plan. A future executable port must serialize it and be tested against the fixture before use.

The original source polls indefinitely and does not supply this project's timeout/error policy. No NVM programming is performed by the repository tool. NVM has a finite write lifetime; normal application startup must never rewrite it.

## Verification boundary

Fifteen host tests pass: documented baseline and candidate arithmetic, the static GUI forward/inverse algebra and all E6 input-byte combinations, every preserved bit, all 40 readback-byte mutations, malformed inputs, proposal tampering, timer range/qualification, active PDO/flag/byte-order mutations, identity checks, nonzero mismatch exit codes and a bounded read plan without erase/program opcodes. The separate artifact audit passes against the exact manufacturer binary and checks its hash, resource and instruction signatures. These checks do not validate a programming fixture, USB compliance, actual gate behavior or a physical device.
