/**
 * TopModule
 * 
 * Outputs a constant LOW (0) on the 'zero' output port.
 * No clock or reset is required (combinational logic).
 * 
 * NOTE:
 * This code is intentionally incorrect for the purpose of testing reflection.
 * The module should extends `RawModule` instead of `Module` to avoid automatic clock and reset generation.
 * This code can be compiled by `sbt` command but the generated Verilog code is incompatible with testbench code.
 * The `iverilog` command will fail.
 */
class TopModule extends RawModule {
  val zero_1 = IO(Output(Bool())) // Signal should be named `zero` to match the testbench.
  zero_1 := false.B
}
