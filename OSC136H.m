classdef OSC136H < handle
    
    properties
        
        % OKFP Dev object for using the Opal Kelly FP Library
        dev
        
    end

    methods
        % OSC136H Constructor
        % Initializes the channel and waveform information to all zeroes.
        % Also loads the OK library, and constructs a dev object that will
        % be used for all library interactions with FrontPanel.
        function obj = OSC136H()
            if ~libisloaded('okFrontPanel')
                loadlibrary('okFrontPanel', 'okFrontPanelDLL.h');
            end
            % Initialize a new OSC136H object
            obj.dev = calllib('okFrontPanel', 'okFrontPanel_Construct');
            fprintf('Successfully loaded okFrontPanel.\n');
        end
        
        % OSC136H Destructor
        % Disconnects from the board to prevent connection issues when
        % using multiple instances of the classes. 
        function delete(this)
             this.Disconnect();
             
        end
        
        % isOpen
        % Checks if we are currently connected to a board.
        function open = isOpen(this)
            open = calllib('okFrontPanel', 'okFrontPanel_IsOpen', this.dev);
        end
               
        % OutputWireInVal
        % Reads the value at a given WireIn endpoint using FP and outputs
        % the 16-bit wire. Useful for checking whether updates worked
        % correctly.
        function OutputWireInVal(this, endpoint)
        	if endpoint > 32
        		fprintf('Out of scope of WireIn\n');
        		return;
        	end
            WIREIN_SIZE = 16;
            buf = libpointer('uint32Ptr', 10);
            calllib('okFrontPanel', 'okFrontPanel_GetWireInValue', this.dev, endpoint, buf);
            fprintf('WireIn %d: ', endpoint);
            fprintf(dec2bin(get(buf, 'Value'), WIREIN_SIZE));
            fprintf('\n');
        end

        function OutputWireOutVal(this, endpoint)
        	if endpoint <= 32
        		fprintf('Out of scope of WireOut\n');
        		return;
        	end
            WIREIN_SIZE = 16;
            buf = libpointer('uint32Ptr', 10);
            calllib('okFrontPanel', 'okFrontPanel_UpdateWireOuts', this.dev);
            buf = calllib('okFrontPanel', 'okFrontPanel_GetWireOutValue', this.dev, endpoint);
            fprintf('WireOut endpoint endpoint %s: ', dec2hex(endpoint));
            fprintf(dec2bin(buf, WIREIN_SIZE));
            fprintf('\n');
        end
        
        % WriteToWireIn
        % Takes an OK FP WireIn endpoint, a beginning bit, a write length,
        % and a value. Writes the first write_length bits of value into the
        % WireIn specified by endpoint, starting at the location begin.
        function WriteToWireIn(this, endpoint, begin, write_length, value)
            % Mask constructed to isolate desired bits.
            mask = (2 ^ write_length) - 1;
            shifter = begin;
            mask = bitshift(mask, shifter);
            val =  bitshift(bitor(0, value), shifter);
            calllib('okFrontPanel', 'okFrontPanel_SetWireInValue', this.dev, endpoint, val, mask);
            calllib('okFrontPanel', 'okFrontPanel_UpdateWireIns', this.dev);
            fprintf('WriteToWireIn %d: %d\n', endpoint, value);
            % pause(0.05);
        end
                
        % Disconnect
        % Attempts to disconnect a connected OK FPGA.
        function ec = Disconnect(this)
           if ~this.isOpen()
              fprintf('No open board to disconnect!\n');
              ec = 0;
              return
           end
           this.SysReset();
           calllib('okFrontPanel', 'okFrontPanel_Close', this.dev);
           if this.isOpen()
               fprintf('Failed to close board\n')
               ec = -1;
               return
           end
           fprintf('Successfully closed board\n')
           ec = 0;
        end
        
        % Configure
        % Takes a filename as a path to the bitfile, and loads it onto the
        % FPGA. The desired bitfile is titled 'config.bit'.
        function ret = Configure(this, filename)
           ret = -1;
           ec = calllib('okFrontPanel', 'okFrontPanel_ConfigureFPGA', this.dev, filename);
           if ec ~= "ok_NoError"
               fprintf('Error loading bitfile\n')
               return
           end
           fprintf("Succesfully loaded bitfile\n");
           
           pll = calllib('okFrontPanel', 'okPLL22150_Construct');
           calllib('okFrontPanel', 'okPLL22150_SetReference', pll, 48.0, 0);
           calllib('okFrontPanel', 'okPLL22150_SetVCOParameters', pll, 512, 125);
           
           calllib('okFrontPanel', 'okPLL22150_SetDiv1', pll, 'ok_DivSrc_VCO', 15);
           calllib('okFrontPanel', 'okPLL22150_SetDiv2', pll, 'ok_DivSrc_VCO', 8);
           
           calllib('okFrontPanel', 'okPLL22150_SetOutputSource', pll, 0, 'ok_ClkSrc22150_Div1ByN');
           calllib('okFrontPanel', 'okPLL22150_SetOutputEnable', pll, 0, 1);
           
           calllib('okFrontPanel', 'okPLL22150_SetOutputSource', pll, 1, 'ok_ClkSrc22150_Div2ByN');
           calllib('okFrontPanel', 'okPLL22150_SetOutputEnable', pll, 1, 1);
           
           calllib('okFrontPanel', 'okFrontPanel_SetPLL22150Configuration', this.dev, pll);
           ret = 0;
        end
        
        % Gets list of serial numbers for all connected boards
        function serials = GetBoardSerials(this)
            serials = 'No connected devices';
            device_count = calllib('okFrontPanel', 'okFrontPanel_GetDeviceCount', this.dev);
            for d = 0:(device_count - 1)
                sn = calllib('okFrontPanel', 'okFrontPanel_GetDeviceListSerial', this.dev, d, blanks(30));
                if ~exist('snlist', 'var')
                    snlist = sn;
                else
                    snlist = char(snlist, sn);
                end
            end
            if exist('snlist', 'var')
                serials = snlist;
            end
        end


        % Connect
        % Connects the board to the first openly available FPGA.
        function ec = Connect(this, serial)
            % For now, all this function does is connect to the first
            % available board.
            ec = 0;
            % serial = this.GetBoardSerials();
            this.dev = calllib('okFrontPanel', 'okFrontPanel_Construct');
            calllib('okFrontPanel', 'okFrontPanel_OpenBySerial', this.dev, serial);
            open = calllib('okFrontPanel', 'okFrontPanel_IsOpen', this.dev);
            if ~open
                fprintf('Failed to open board\n')
                ec = -1;
                return
            end
            fprintf('Successfully opened board\n')
            % this.Configure('OSC1_LITE_Control.bit');
				         %    pause(0.5);
				         %    if this.SysReset() == -1 || this.SetControlReg() == -1
				         %    	fprintf('Failed to initialize.\n')
				         %    	return
				         %    end
        					% this.WriteToWireIn(hex2dec('17'), 0, 16, 0);
        end
       
        function ec = ConnectToFirst(this)
            % For now, all this function does is connect to the first
            % available board.
            ec = 0;
            serial = this.GetBoardSerials();
            this.dev = calllib('okFrontPanel', 'okFrontPanel_Construct');
            calllib('okFrontPanel', 'okFrontPanel_OpenBySerial', this.dev, serial);
            open = calllib('okFrontPanel', 'okFrontPanel_IsOpen', this.dev);
            if ~open
                fprintf('Failed to open board\n')
                ec = -1;
                return
            end
            fprintf('Successfully opened board\n')
%             this.Configure('OSC1_LITE_Control.bit');
			pause(0.5);
			if this.Configure('OSC1_LITE_Control.bit') == -1 || this.SysReset() == -1 || this.SetControlReg() == -1
				fprintf('Failed to initialize.\n')
				return
			end
        	this.WriteToWireIn(hex2dec('17'), 0, 16, 0);
        end
        
        function SetAllZero(this)	
            	this.WriteToWireIn(hex2dec('00'), 0, 16, 0);
            	this.WriteToWireIn(hex2dec('01'), 0, 16, 1);
            for channel = 0: 11
            	this.WriteToWireIn(hex2dec('03') + channel, 0, 16, 0);
            end
        end

        function SetAllHigh(this)	
            	this.WriteToWireIn(hex2dec('00'), 0, 16, 0);
            	this.WriteToWireIn(hex2dec('01'), 0, 16, 1);
            for channel = 0: 11
            	this.WriteToWireIn(hex2dec('03') + channel, 0, 16, 2731);
            end
        end
        
        function SetWaveformParams(this, channel, mode, amp, period, pulse_width, n_pulses)
            this.WriteToWireIn(3, 0, 16, convergent(pulse_width / (2^11) * 13107200));
            this.WriteToWireIn(4, 0, 16, convergent(period / (2^11) * 13107200));
            mult = [1,3,13,25,50];
            wirein = amp / 24000 * 65536 / mult(mode+1);
            this.WriteToWireIn(5, 0, 16, convergent(wirein));
            this.WriteToWireIn(7, 0, 16, n_pulses);
            this.WriteToWireIn(6, 0, 16, bitor(mode, bitsll(channel-1, 4)));
            pause(0.01);
            this.WriteToWireIn(6, 8, 1, 1);
            pause(0.01);
        end

        function SetAll(this)
           % Cth = zeros(1:12);
           % Option = zeros(1:12);
           % amplitude = zeros(1:12);
           % Cmax = zeros(1:12);
      
            	this.WriteToWireIn(hex2dec('00'), 0, 16, 0);
            	this.WriteToWireIn(hex2dec('01'), 0, 16, 1);
            for i = 1:12
              this.SetWaveformParams(i, 0, 1000, 2, 1)
              %  Cth(i) = 50000*i;
              %%  Cmax(i) = 200;
              %  Option(i) = 4;
              %  switch Option(i)
              %      case 0
              %          amplitude(i) =  2^12;
              %      case 1
              %          amplitude(i) = floor(2^12/3);
              %      case 2
              %          amplitude(i) = floor(2^12/13);
              %      case 3 
              %          amplitude(i) = floor(2^12/25);
              %      case 4 
              %          amplitude(i) = floor(2^12/50);
              %      otherwise
              %          amplitude(i) = 0;
              %  end
            end
      
%            	this.WriteToWireIn(hex2dec('00'), 0, 16, 0);
%            	this.WriteToWireIn(hex2dec('01'), 0, 16, 1);
%            for channel = 0: 11
%            	this.WriteToWireIn(hex2dec('03') + channel, 0, 16, amplitude(channel+1));%input amplitude
%            end
%            for channel = 0:5
%                this.WriteToWireIn(hex2dec('0f') + channel, 0, 16, Cth(channel+1));%input Cth part 1
%                this.WriteToWireIn(hex2dec('18') + channel, 0, 16, Cth(channel+7));%input Cth part 2
%            end
%            for channel  = 0:2
%                this.WriteToWireIn(hex2dec('1e') + channel,0,16,Option(channel*4+1) + Option(channel*4+2)*2^4 + Option(channel*4+3)*2^8 + Option(channel*4+4)*2^12);
%            end
        end

        
        
        
        
        
        
        % Reset the electronics, as well as setting all parameters to 0.
        function ec = SysReset(this)
            ec = 0;
            open = calllib('okFrontPanel', 'okFrontPanel_IsOpen', this.dev);
            if ~open
                fprintf('Failed to open board\n')
                ec = -1;
                return
            end
            
            fprintf('Reseting system to default state\n')

            this.WriteToWireIn(hex2dec('01'), 0, 16, 4);
            this.WriteToWireIn(hex2dec('00'), 0, 16, 1);

            this.WriteToWireIn(hex2dec('01'), 0, 16, 0);
            this.WriteToWireIn(hex2dec('02'), 0, 16, 0);
            
            this.SetAllZero();

            this.WriteToWireIn(hex2dec('00'), 0, 16, 0);
            this.WriteToWireIn(hex2dec('01'), 0, 16, 0);
            this.WriteToWireIn(hex2dec('02'), 0, 16, 0);
        end      

        function ec = EnableWrite(this, channel, value)
            ec = 0;
            open = calllib('okFrontPanel', 'okFrontPanel_IsOpen', this.dev);
            if ~open
                fprintf('Failed to Enable Write\n')
                ec = -1;
                return
            end
            fprintf('Writing %d to the register\n', value)
            this.WriteToWireIn(hex2dec('03') + channel, 0, 16, value);	% Update the value first to avoid potential data loss
            % this.WriteToWireIn(hex2dec('00'), 0, 16, 1);		
            this.WriteToWireIn(hex2dec('00'), 0, 16, 0);
            % pause(0.1);
            this.WriteToWireIn(hex2dec('01'), 0, 16, 1);
            % pause(0.1);
            % this.SetNoop();
        end

        function ec = EnableRead(this)
            ec = 0;
            open = calllib('okFrontPanel', 'okFrontPanel_IsOpen', this.dev);
            if ~open
                fprintf('Failed to Enable Read\n')
                ec = -1;
                return
            end
            fprintf('Reading from the register\n')
            this.WriteToWireIn(hex2dec('00'), 0, 16, 0);
            % pause(0.1);
            this.WriteToWireIn(hex2dec('01'), 0, 16, 2);
            % pause(0.1);
            this.SetNoop();
        end

        function ec = EnableClear(this)
            ec = 0;
            open = calllib('okFrontPanel', 'okFrontPanel_IsOpen', this.dev);
            if ~open
                fprintf('Failed to Enable Clear\n')
                ec = -1;
                return
            end
            fprintf('Clearing the register\n')
            this.WriteToWireIn(hex2dec('00'), 0, 16, 0);
            this.WriteToWireIn(hex2dec('02'), 0, 16, 1);
            % pause(0.1);
            this.WriteToWireIn(hex2dec('02'), 0, 16, 0);
            this.SetNoop();
        end    

        function ec = SetControlReg(this)
            ec = 0;
            open = calllib('okFrontPanel', 'okFrontPanel_IsOpen', this.dev);
            if ~open
                fprintf('Failed to Set Control Register\n')
                ec = -1;
                return
            end
            fprintf('Setting Control Register\n')
            this.WriteToWireIn(hex2dec('00'), 0, 16, 0);
            this.WriteToWireIn(hex2dec('01'), 0, 16, 5);
            % pause(0.1);
            this.WriteToWireIn(hex2dec('01'), 0, 16, 3);
            % pause(0.1);
            this.WriteToWireIn(hex2dec('01'), 0, 16, 0);
            this.SetNoop();
        end    

        function SetNoop(this)
        	% pause(0.1);
            this.WriteToWireIn(hex2dec('01'), 0, 16, 0);
        end

        function MatTrigger(this, cus_time)
            this.WriteToWireIn(hex2dec('00'), 0, 16, 0);
            this.WriteToWireIn(hex2dec('01'), 0, 16, 1);
            for i = 0: cus_time
                for channel = 0: 11
            	this.WriteToWireIn(hex2dec('03') + channel, 0, 16, 2^14);
            	this.WriteToWireIn(hex2dec('03') + channel, 0, 16, 0);
                end
            end
        end

        function tlines = SavePipeFromFile(this, filename)
            fprintf('Saving pipe data from %s\n', filename)
            fd = fopen(filename, 'r');
            if fd == -1
               fprintf('Error opening pipe data file.\n');
               return
            end
            tline = fgetl(fd);
            tlines = cell(0,1);
            while ischar(tline)
                tlines{end+1,1} = str2num(tline);
                tline = fgetl(fd);
            end
            tlines = cell2mat(tlines);
            fclose(fd);
        end    

        function ec = TriggerPipe(this, channel, num_of_pulses, cont, pipe_data)
            ec = -1;
            if ~this.isOpen()
                fprintf('Board not open\n')
                return
            end
            % [txtfile, path] = uigetfile('*.cwave', 'Select the .cwave file');
            % if ~isequal(txtfile, 0)
            %     try
            %     pipe_data = this.SavePipeFromFile(strcat(path, txtfile));
            %     catch
            %        errordlg('File error.', 'Type Error');
            %     end
            % end

            this.WriteToWireIn(hex2dec('00'), 0, 16, 1);
            this.WriteToWireIn(hex2dec('00'), 0, 16, 0);

            if cont == 0
                this.WriteToWireIn(hex2dec('15'), 0, 16, numel(pipe_data));
            	this.WriteToWireIn(hex2dec('16'), 0, 16, num_of_pulses);
            else
                this.WriteToWireIn(hex2dec('15'), 0, 16, numel(pipe_data));
            	this.WriteToWireIn(hex2dec('16'), 0, 16, 65535);
            end
            
            SIZE = numel(pipe_data);
            if (SIZE <= 1 || SIZE > 32768)
                errordlg('Error: Invalid pipe data size. Valid size is [2, 32768]. Aborted.', 'Type Error');
                return
            end
            
            data_out(2 * SIZE, 1) = uint8(0);
            for i = 1:SIZE
                if pipe_data(i) > 2^17
                    pipe_data(i) = 2^17 - 1;
                end
                if pipe_data(i) < 0
                    pipe_data(i) = 0;
                end
                data_out(2 * i - 1) = uint8(floor(pipe_data(i) / 256)); 
                data_out(2 * i) = uint8(mod(pipe_data(i), 256)); 
                fprintf('Write %d into memory\n', data_out(2 * i - 1));
                fprintf('Write %d into memory\n', data_out(2 * i));
            end

            success_ret = calllib('okFrontPanel', 'okFrontPanel_WriteToPipeIn', this.dev, hex2dec('80'), 2 * SIZE, data_out);
            fprintf('Success %d \n', success_ret);
            
            this.WriteToWireIn(hex2dec('00'), 0, 16, 2^16-2);    % switch to pipe mode
            this.WriteToWireIn(hex2dec('01'), 0, 16, 1);    % switch to write mode

            persistent buf pv;
            buf(2 * SIZE, 1) = uint8(0);
            pv = libpointer('uint8Ptr', buf);
            success_ret = calllib('okFrontPanel', 'okFrontPanel_ReadFromPipeOut', this.dev, hex2dec('A0'), 2 * SIZE, pv);
            fprintf('Success %d \n',   success_ret);
            
        % epvalue = get(pv, 'Value');
        % pipe_out_data = zeros(SIZE, 1);
        % for i = 1:SIZE
        %     pipe_out_data(i) = uint16(epvalue(2 * i - 1))* 256 + uint16(epvalue(2 * i));
        %     fprintf('Read %d \n',   pipe_out_data(i));
        % end
            ec = 0;
        end

    end
end


