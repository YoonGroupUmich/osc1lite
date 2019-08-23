//------------------------------------------------------------------------
// FrontPanel Library Module Declarations (Verilog)
// XEM7001
//
// IDELAY and IODELAY fixed delays were determined empirically to meet
// timing for particular devices on particular products.
//
// Copyright (c) 2004-2015 Opal Kelly Incorporated
// $Rev: 980 $ $Date: 2015-07-27 14:41:30 -0700 $
//------------------------------------------------------------------------

`default_nettype none
module okHost
	(
	input  wire [7:0]  hi_in,
	output wire [1:0]  hi_out,
	inout  wire [15:0] hi_inout,
	inout  wire        hi_aa,
	output wire        ti_clk,
	output wire [30:0] ok1,
	input  wire [16:0] ok2
	);

	wire [24:0] okHC;
	wire [20:0] okCH;
		
	wire [15:0] iobf0_hi_datain;
	wire [15:0] hi_datain;
	
	wire [15:0] fdreout0_hi_dataout;
	wire [15:0] fdreout1_hi_drive; 
	
	assign okHC[0]     = ti_clk;
	assign okHC[7:1]   = hi_in[7:1];
	assign okHC[23:8]  = hi_datain;

	// Clock buffer for the Host Interface clock.
	wire mmcm0_clk0,mmcm0_clk0_bufg;
	wire mmcm0_clkfb,mmcm0_clkfb_bufg;
	wire mmcm0_locked;
	wire hi_in0_ibufg;

	IBUFG hi_in0_bufg (.I(hi_in[0]), .O(hi_in0_ibufg));

	MMCME2_BASE #(
		.BANDWIDTH("OPTIMIZED"),   // Jitter programming (OPTIMIZED, HIGH, LOW)
		.CLKFBOUT_MULT_F(20),      // Multiply value for all CLKOUT (2.000-64.000).
		.CLKFBOUT_PHASE(0.0),      // Phase offset in degrees of CLKFB (-360.000-360.000).
		.CLKIN1_PERIOD(20.833),    // Input clock period in ns to ps resolution (i.e. 33.333 is 30 MHz).
		.CLKOUT0_DIVIDE_F(20.0),   // Divide amount for CLKOUT0 (1.000-128.000).
		.CLKOUT0_PHASE(4.5),       // Phase offset for each CLKOUT (-360.000-360.000).
		.DIVCLK_DIVIDE(1),         // Master division value (1-106)
		.REF_JITTER1(0.0),         // Reference input jitter in UI (0.000-0.999). 
		.STARTUP_WAIT("FALSE")     // Delays DONE until MMCM is locked (FALSE, TRUE)
	)
	mmcm0 (
		.CLKOUT0(mmcm0_clk0),      // 1-bit output: CLKOUT0
		.CLKFBOUT(mmcm0_clkfb),    // 1-bit output: Feedback clock
		.LOCKED(mmcm0_locked),     // 1-bit output: LOCK
		.CLKIN1(hi_in0_ibufg),     // 1-bit input: Clock
		.RST(1'b0),                // 1-bit input: Reset
		.CLKFBIN(mmcm0_clkfb_bufg) // 1-bit input: Feedback clock
	);

	BUFG mmcm0_bufg   (.I(mmcm0_clk0), .O(ti_clk));
	BUFG mmcm0fb_bufg (.I(mmcm0_clkfb), .O(mmcm0_clkfb_bufg));
	
	//IOBs for hi_inout
	genvar i;
	generate
		for (i=0; i<16; i=i+1) begin : delays
			
			IOBUF iobf0 (
				.IO(hi_inout[i]),
				.I(fdreout0_hi_dataout[i]), 
				.O(iobf0_hi_datain[i]), 
				.T(fdreout1_hi_drive[i]) 
			);

			(* IOB = "true" *)
			FDRE fdrein0 (
				.D              (iobf0_hi_datain[i]),
				.C              (ti_clk),
				.CE             (1'b1),
				.R              (1'b0),
				.Q              (hi_datain[i])
			);

			// Output Registering
			(* IOB = "true" *)
			FDRE fdreout0 (
				.D              (okCH[i+3]),
				.C              (ti_clk),
				.CE             (1'b1),
				.R              (1'b0),
				.Q              (fdreout0_hi_dataout[i])
			);

			(* IOB = "true" *)
			FDRE fdreout1 (
				.D              (~okCH[2]),
				.C              (ti_clk),
				.CE             (1'b1),
				.R              (1'b0),
				.Q              (fdreout1_hi_drive[i])
			);

		end
	endgenerate
	
	OBUF obuf0(.I(okCH[0]), .O(hi_out[0]));
	OBUF obuf1(.I(okCH[1]), .O(hi_out[1]));
	IOBUF tbuf(.I(okCH[19]), .O(okHC[24]), .T(okCH[20]), .IO(hi_aa));

	okCoreHarness core0(.okHC(okHC), .okCH(okCH), .ok1(ok1), .ok2(ok2));
endmodule

module okWireOR # (parameter N = 1)	(
	output reg  [16:0]     ok2,
	input  wire [N*17-1:0] ok2s
	);

	integer i;
	always @(ok2s)
	begin
		ok2 = 0;
		for (i=0; i<N; i=i+1) begin: wireOR
			ok2 = ok2 | ok2s[ i*17 +: 17 ];
		end
	end
endmodule
