`timescale 1ns / 1ps
`default_nettype none
/////////////////////////////////////////////////
// OSC1 - LITE
// Version 1.0.0
// Yoon's Lab - U of M
/////////////////////////////////////////////////


module OSC1_LITE_Control(
	input  wire [7:0]  hi_in,
	output wire [1:0]  hi_out,
	inout  wire [15:0] hi_inout,
	inout  wire        hi_aa,
	output wire        hi_muxsel,	
	input  wire		   clk,
	output wire [7:0]  led,	
	output wire [11:0] 	clear,
    output wire [11:0] 	latch,
    output wire [11:0] 	sclk,
    output wire [11:0] 	din,
    input wire [11:0] 	sdo_bit,
	input wire [11:0] 	trig_in_external,
    output wire [11:0] 	trig_out
	);

wire khan;

// Target interface bus:
wire		ti_clk;
wire [30:0]	ok1;
wire [16:0]	ok2;

wire [2:0]	sys_ctrl_pad1;
wire [12:0]	sys_ctrl_pad2;
wire [14:0]	sys_ctrl_pad3;
wire [12:0]	sys_ctrl_pad4;

reg	 [6:0] 	clk_counter;
wire [6:0]	division;

wire [11:0] trig_in_pc;
wire [15:0] data_from_user_trig_in;

wire 		rst;
wire [11:0] pipe;	
wire [2:0]	div_mode;
wire [2:0]	mode;
wire 		clear_request;

// waveform parameter
wire		data_trigger;
wire [3:0] 	data_mode;
wire [3:0] 	addr;
reg [191:0] amplitude;
reg [239:0] pulse_width; 
reg [47:0]  option;
reg [239:0] wave_period;
reg [191:0] wave_number_of_pulse;
reg [11:0] 	external_trigger_valid;

// data from GUI
wire [15:0] data_from_user_pulse_width;
wire [15:0] data_from_user_period;
wire [15:0] data_from_user_pulse_period;
wire [15:0] data_from_user_amp;
wire [15:0] data_from_user_mode;
wire [15:0] data_from_user_number_of_pulse;
wire [15:0] data_from_user_trig_out_valid;
wire [15:0] data_from_user_disable;
wire [15:0] data_from_user_enable;
wire [15:0] data_from_user_trig_source;
wire [15:0] data_from_user_trig_mode;

// Instantiation wire
wire [11:0] trig_out_valid;
wire [11:0] channel_disable;
wire [11:0] channel_enable;
wire [15:0] overlap_trig_in;
wire [15:0] disable_no_trig;
wire [11:0] trig_source;
wire [11:0] trig_mode;

// pipe
wire 		pipe_in_write_enable;
wire 		pipe_out_read_enable;
wire [15:0] pipe_in_write_data;
wire [15:0] pipe_out_read_data;
wire [15:0] period;
wire [15:0] num_of_pulses;
wire [11:0]	spi_pipe_clk;

// Instantiation wire
wire 		clk_pulse;
wire [191:0] result; 
wire [11:0] flag;
wire [11:0] resetflag;
wire [23:0] counter2spi;
wire [11:0] new_trig_in;
wire [11:0] no_trig;
wire [11:0] config_counter;
wire [59:0] alarm_out;
wire [15:0] alarm_out_0; // channel 0-2
wire [15:0] alarm_out_3; // channel 3-5
wire [15:0] alarm_out_6; // channel 6-8
wire [15:0] alarm_out_9; // channel 9-11
wire [15:0] flag_out;
wire [11:0] channel_is_disable;
wire [15:0] channel_is_disable_out;
wire [11:0] trig_in_shank;

// signals to GUI control
assign alarm_out_0 = {1'b0, alarm_out[14:0]};
assign alarm_out_3 = {1'b0, alarm_out[29:15]};
assign alarm_out_6 = {1'b0, alarm_out[44:30]};
assign alarm_out_9 = {1'b0, alarm_out[59:45]};
assign flag_out = {4'b0, flag[11:0]};
assign channel_is_disable_out = {4'b0, channel_is_disable[11:0]};
assign overlap_trig_in = {4'b0, new_trig_in[11:0]};
assign disable_no_trig = {4'b0, no_trig[11:0]};

// signals from GUI control
assign data_mode = data_from_user_mode[3:0];
assign addr = data_from_user_mode[7:4];
assign data_trigger = data_from_user_mode[8];
assign trig_source = data_from_user_trig_source[11:0];
assign trig_mode = data_from_user_trig_mode[11:0];
assign trig_in_pc = data_from_user_trig_in[11:0];
assign trig_out_valid = data_from_user_trig_out_valid[11:0];
assign channel_disable = data_from_user_disable[11:0];
assign channel_enable = data_from_user_enable[11:0];
assign hi_muxsel = 1'b0;

// external trig_in re-mapping due to different mapping order on board and GUI
// trig_out re-mapping is done in the constraint file 
// Shank 1
assign trig_in_shank[7] = trig_in_external[0];
assign trig_in_shank[2] = trig_in_external[1];
assign trig_in_shank[8] = trig_in_external[2];
// Shank 2
assign trig_in_shank[0] = trig_in_external[3];
assign trig_in_shank[6] = trig_in_external[4];
assign trig_in_shank[1] = trig_in_external[5];
// Shank 3
assign trig_in_shank[10] = trig_in_external[6];
assign trig_in_shank[5] = trig_in_external[7];
assign trig_in_shank[11] = trig_in_external[8];
// Shank 4
assign trig_in_shank[3] = trig_in_external[9];
assign trig_in_shank[9] = trig_in_external[10];
assign trig_in_shank[4] = trig_in_external[11];

// clock devider
assign division = (div_mode == 3'b001) ? 7'b0000100 : (div_mode == 3'b010) ? 7'b0010100 : (div_mode == 3'b011) ? 7'b0101000 : 7'b1000000;
assign clk_pulse = (div_mode == 3'b000) ? clk : (clk_counter == 0);

// save the waveform parameter data from GUI 
always @ (posedge data_trigger) begin
	amplitude[16*addr +: 16] = data_from_user_amp;
	pulse_width[20*addr +: 16] = data_from_user_pulse_width;
	pulse_width[(20*addr+16) +: 4] = data_from_user_pulse_period[3:0];
	wave_period[20*addr +: 16] = data_from_user_period;
	wave_period[(20*addr+16) +: 4] = data_from_user_pulse_period[11:8];
	option[4*addr +: 4] = data_mode;
	wave_number_of_pulse[16*addr +: 16] = data_from_user_number_of_pulse;
end

read_input calc[11:0](
	// input 
    .clk(clk_pulse),
    .rst(rst),
	.new_trig_in(new_trig_in[11:0]),
    .amplitude(amplitude[191:0]),
    .Cmax(wave_period[239:0]),
    .Cth(pulse_width[239:0]),
    .Option(option[47:0]),
	.wave_number_of_pulse(wave_number_of_pulse),
	.flag(flag[11:0]),
	.trig_out_valid(trig_out_valid[11:0]),
	.config_counter(config_counter[11:0]),
	.channel_disable(channel_disable[11:0]),
	.trig_mode(trig_mode[11:0]),
	// output 
    .result(result),
    .resetflag(resetflag[11:0]),
	.trig_out(trig_out[11:0]),
	.counter2spi(counter2spi)
);

trigger_in dotrigger[11:0](
	// input
	.trigger_in_pc(trig_in_pc[11:0]),
	.trigger_in_external(trig_in_shank[11:0]),
	.trig_source(trig_source[11:0]),
    .clock(clk_pulse),
    .reset(rst),
    .resetflag(resetflag[11:0]),
	.channel_disable(channel_disable[11:0]),
	.channel_is_disable(channel_is_disable[11:0]),
	// output
    .flag(flag[11:0]),
	.new_trig(new_trig_in[11:0]),
	.no_trig(no_trig[11:0])
    );


spi_controller dac_spi0 [11:0](
	// input 
	.clk(clk_pulse), 
	.rst(rst),	
	.mode_pc(mode), 
	.clear_request(clear_request),		
	.pipe(pipe[11:0]),
	.data_from_memory({pipe_out_read_data[7:0],pipe_out_read_data[15:8]}),
	.data_from_user(result),	
	.sdo_bit(sdo_bit),	
	.counter2spi(counter2spi),
	.no_trig(no_trig[11:0]),
	.channel_disable(channel_disable[11:0]),
	.channel_enable(channel_enable[11:0]),
	// output
	.clear(clear),	
	.latch(latch),	
	.sclk(sclk),	
	.din(din),
	.spi_pipe_clk(spi_pipe_clk),
	.alarm_out(alarm_out),
	.config_counter(config_counter[11:0]),
	.channel_is_disable(channel_is_disable[11:0])
    );

amp_pipe my_amp_pipe(
	// input
	.ti_clk(clk_pulse),
	.reset(rst),
	.clk(spi_pipe_clk[0]),
	.period(period),
	.num_of_pulses(num_of_pulses),
	.pipe_in_write_trigger(pipe_in_write_enable),
	.pipe_in_write_data(pipe_in_write_data),
	.pipe_out_read_trigger(pipe_out_read_enable),
	// output 
	.pipe_out_read_data(pipe_out_read_data),
	.khan(khan)	
);

okHost okHI(
	.hi_in(hi_in), .hi_out(hi_out), .hi_inout(hi_inout), .hi_aa(hi_aa), .ti_clk(ti_clk),
	.ok1(ok1), .ok2(ok2));

wire [17*10-1:0]  ok2x;
okWireOR # (.N(10)) wireOR (ok2, ok2x);
okWireIn	wi00 (.ok1(ok1), .ep_addr(8'h00), .ep_dataout({sys_ctrl_pad1, pipe, rst}));
okWireIn	wi01 (.ok1(ok1), .ep_addr(8'h01), .ep_dataout({sys_ctrl_pad2, mode}));
okWireIn	wi02 (.ok1(ok1), .ep_addr(8'h02), .ep_dataout({sys_ctrl_pad3,clear_request}));
okWireIn	wi03 (.ok1(ok1), .ep_addr(8'h03), .ep_dataout(data_from_user_pulse_width[15:0]));
okWireIn	wi04 (.ok1(ok1), .ep_addr(8'h04), .ep_dataout(data_from_user_period[15:0]));
okWireIn	wi05 (.ok1(ok1), .ep_addr(8'h05), .ep_dataout(data_from_user_amp[15:0]));
okWireIn	wi06 (.ok1(ok1), .ep_addr(8'h06), .ep_dataout(data_from_user_mode[15:0]));
okWireIn	wi07 (.ok1(ok1), .ep_addr(8'h07), .ep_dataout(data_from_user_number_of_pulse[15:0]));
okWireIn	wi08 (.ok1(ok1), .ep_addr(8'h08), .ep_dataout(data_from_user_trig_source[15:0])); 		// 0 is PC trigger, 1 is external trigger
okWireIn	wi09 (.ok1(ok1), .ep_addr(8'h09), .ep_dataout(data_from_user_trig_out_valid[15:0])); 	// 0 is not valid, 1 is valid
okWireIn	wi0a (.ok1(ok1), .ep_addr(8'h0a), .ep_dataout(data_from_user_pulse_period[15:0]));
okWireIn	wi0b (.ok1(ok1), .ep_addr(8'h0b), .ep_dataout(data_from_user_trig_mode[15:0])); 		// 0 is one-shot, 1 is continuous
okWireIn	wi15 (.ok1(ok1), .ep_addr(8'h15), .ep_dataout(period[15:0]));
okWireIn	wi16 (.ok1(ok1), .ep_addr(8'h16), .ep_dataout(num_of_pulses[15:0]));
okWireIn	wi17 (.ok1(ok1), .ep_addr(8'h17), .ep_dataout({sys_ctrl_pad4, div_mode}));

okTriggerIn trigIn53 (.ok1(ok1),.ep_addr(8'h53), .ep_clk(clk_pulse), .ep_trigger(data_from_user_enable[15:0])); // enable
okTriggerIn trigIn54 (.ok1(ok1),.ep_addr(8'h54), .ep_clk(clk_pulse), .ep_trigger(data_from_user_disable[15:0])); // disable
okTriggerIn trigIn55 (.ok1(ok1),.ep_addr(8'h55), .ep_clk(clk_pulse), .ep_trigger(data_from_user_trig_in[15:0])); 

okPipeIn  pi80 (.ok1(ok1), .ok2(ok2x[ 0*17 +: 17 ]), .ep_addr(8'h80), .ep_write(pipe_in_write_enable), .ep_dataout(pipe_in_write_data));
okPipeOut poa0 (.ok1(ok1), .ok2(ok2x[ 1*17 +: 17 ]), .ep_addr(8'hA0), .ep_read(pipe_out_read_enable), .ep_datain(pipe_out_read_data));

okTriggerOut trigOut6a (.ok1(ok1), .ok2(ok2x[ 2*17 +: 17 ]),.ep_addr(8'h6A), .ep_clk(clk_pulse), .ep_trigger(overlap_trig_in));
okTriggerOut trigOut6b (.ok1(ok1), .ok2(ok2x[ 3*17 +: 17 ]),.ep_addr(8'h6B), .ep_clk(clk_pulse), .ep_trigger(alarm_out_0));
okTriggerOut trigOut6c (.ok1(ok1), .ok2(ok2x[ 4*17 +: 17 ]),.ep_addr(8'h6C), .ep_clk(clk_pulse), .ep_trigger(alarm_out_3));
okTriggerOut trigOut6d (.ok1(ok1), .ok2(ok2x[ 5*17 +: 17 ]),.ep_addr(8'h6D), .ep_clk(clk_pulse), .ep_trigger(alarm_out_6));
okTriggerOut trigOut6e (.ok1(ok1), .ok2(ok2x[ 6*17 +: 17 ]),.ep_addr(8'h6E), .ep_clk(clk_pulse), .ep_trigger(alarm_out_9));

okWireOut wo21 (.ok1(ok1), .ok2(ok2x[ 7*17 +: 17 ]), .ep_addr(8'h21), .ep_datain(flag_out));
okWireOut wo22 (.ok1(ok1), .ok2(ok2x[ 8*17 +: 17 ]), .ep_addr(8'h22), .ep_datain(channel_is_disable_out));

okTriggerOut trigOut69 (.ok1(ok1), .ok2(ok2x[ 9*17 +: 17 ]),.ep_addr(8'h69), .ep_clk(clk_pulse), .ep_trigger(disable_no_trig));

always @ (posedge clk or posedge rst) begin
	if(rst) begin
		clk_counter <= 0;
	end else if(clk_counter < division)begin
		clk_counter <= clk_counter + 1;
	end else begin
		clk_counter <= 0;
	end
end

endmodule