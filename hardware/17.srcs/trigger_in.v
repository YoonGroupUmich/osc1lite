`timescale 1ns / 1ps
/////////////////////////////////////////////////
// OSC1 - LITE
// Version 1.0.0
// Yoon's Lab - U of M
/////////////////////////////////////////////////


module trigger_in(
	input wire trigger_in_pc,		// PC mode trigger in
	input wire trigger_in_external,	// enternal mode trigger in
	input wire trig_source,			// 0 is PC trigger, 1 is external trigger
	input wire clock,				// input clock
	input wire reset,				// Opal Kelly reset
	input wire resetflag,			// 1 if request for no output waveform
	input wire channel_disable,		// 1 if request to disable the channel
	input wire channel_is_disable,	// 1 if the channel status is disabled
	
	output reg flag,				// 1 to output waveform
	output reg new_trig				// 1 if detect overlapped trigger in
    );
	
	wire trigger_in;
	wire present_stage;
    reg previous_stage;
	wire next_flag;
	reg prev_trig;
	reg prev_flag;
	reg [31:0] counter;
	
	assign trigger_in = channel_is_disable ? 1'b0 
					  : (trig_source == 1'b1) ? trigger_in_external 
					  : trigger_in_pc;
	assign next_flag = flag;

	always @ (negedge clock) begin
		if (trigger_in) begin
			prev_trig <= 1'b1;
		end else begin
			prev_trig <= 1'b0;
		end
	end
	
	always @ (negedge clock) begin
		if (reset | resetflag | channel_disable | channel_is_disable) begin
			prev_flag <= 1'b0;
		end else begin
			prev_flag <= flag;
		end
		
		if (reset | resetflag| channel_disable | channel_is_disable) begin
			flag <= 1'b0;
		end else if (trigger_in && ~prev_trig) begin
			flag <= 1'b1;
		end else begin
			flag <= next_flag;			
		end
	end
	
	always @ (negedge clock) begin
		if (reset | resetflag | channel_disable | channel_is_disable) new_trig <= 1'b0;
		else if (trigger_in && ~prev_trig && prev_flag) new_trig <= 1'b1;
		else new_trig <= 1'b0;
	end
	
	always @ (negedge clock) begin
		if (reset | flag | channel_disable | channel_is_disable) begin
			counter <= 0;
		end else begin
			counter <= counter + 1;
		end
	end
	
endmodule