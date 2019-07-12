classdef OSCGUI < handle
    
    properties        
      os
      f
      
      pipe_f
      
      num_pipe_pulse
      pipe_data
      
      temp_num_pipe_pulse
      temp_pipe_data
      
      serial_selector
      
      Channel_WF_selectors
      Channel_Trig_selectors
      
      WF_pulse_selectors
      WF_period_selectors
      WF_amp_selectors
      WF_pw_selectors
      
      toggle_button
      push_button
      
      load_parameter_button
      save_parameter_button
      pipe_button
      reset
      connected
      connected_serial_name

      radio_buttons

      
    end
    
    methods
        function obj = OSCGUI()
            obj.f = figure('Name', 'OSC136H Stim Control', 'NumberTitle', 'off', 'Visible','off','Units', 'characters', 'Position',[0 0 400 80]);
            set(obj.f, 'MenuBar', 'none');
            set(obj.f, 'ToolBar', 'none');
            
            obj.pipe_f = figure('Name', 'OSC136H Custom waveform Initialization', 'NumberTitle', 'off', 'Visible','off','Units', 'characters', 'Position',[5 5 210 56]);
            set(obj.pipe_f, 'MenuBar', 'none');
            set(obj.pipe_f, 'ToolBar', 'none');
            
            obj.os = OSC136H();
            obj.ResetGUIdisplay();
            
            obj.f.Visible = 'on';
            set(obj.f,'CloseRequestFcn',@(h,e)obj.CloseRequestCallback);
            set(obj.pipe_f,'CloseRequestFcn',@(h,e)obj.PipeCloseRequestCallback);
            
            obj.DetectBoard();
        end
        
        function delete(this)
            this.os.delete();
        end
        
        function ThrowException(this)
            if(~this.os.isOpen())
                errordlg('Invalid operation. Board is not connected. Windows reset', 'Type Error');
                this.os.Disconnect();
                this.os = OSC136H();
                this.ResetGUIdisplay();
                this.DetectBoard();
            end
        end
        
        function ResetGUIdisplay(this)
                this.Channel_WF_selectors = zeros(3, 12);
                this.Channel_Trig_selectors = zeros(3, 12);
                this.WF_pulse_selectors = zeros(4, 1);
                this.WF_period_selectors = zeros(4, 1);
                this.WF_amp_selectors = zeros(4, 1);
                this.WF_pw_selectors = zeros(4, 1);
                this.num_pipe_pulse = 1;
                this.pipe_data = [0;0];
                this.temp_num_pipe_pulse = 1;
                this.temp_pipe_data = {0;0};
                this.connected = 0;
                this.connected_serial_name = 'No connected devices'; 
                this.CreateSetup();
                this.CreateHeadstagePanels();
                this.CreateWaveformPanels();            
        end
        
        function CloseRequestCallback(hObject,eventdata)
             if(ishandle(hObject.pipe_f))
                hObject.pipe_f.Visible = 'off';
             end
             hObject.f.Visible = 'off';
             hObject.delete();
        end
                
       function PipeCloseRequestCallback(hObject,eventdata)
             hObject.temp_num_pipe_pulse = hObject.num_pipe_pulse;
             hObject.temp_pipe_data = hObject.pipe_data;
             hObject.pipe_f.Visible = 'off';
             fprintf("Custom waveform initilization canceled. No changes will be applied.\n");
       end
        
       function DetectBoard(this)
          try
            while(this.connected == 0)                
            pause(1);
            temp = this.os.GetBoardSerials();
            set(this.serial_selector, 'String', temp);
            end
            set(this.serial_selector,'Enable','off','String',this.connected_serial_name);
          
          catch
            fprintf("Detection of Board was aborted by the user.\n");
          end
       end
       
        function CreateHeadstagePanels(this)
              tabgp = uitabgroup(this.f, 'Position', [.4 .15 .55 .80]);
              tab1 = uitab(tabgp,'Title', "Headstage 1");
              
              this.PopulateHeadstagePanel(tab1, 1);
        end
     
        function PopulateHeadstagePanel(this, parent, hs)
            for chan = 1:12
                LED(chan) = uicontrol('Style', 'text', 'FontSize', 9, 'String', strcat(' LED ', num2str(mod(chan - 1, 3) + 1)), 'Units', 'normalized', 'Parent',... 
                            parent, 'Position', [.039 .90 - (chan - 1) * (1/13) .13 1/28]);                        
                % this.Channel_WF_selectors(hs, chan) = uicontrol('Style', 'popupmenu', 'String', {'Waveform 1', 'Waveform 2', 'Waveform 3', 'Waveform 4','Custom waveform'}, 'Units', 'normalized', 'Parent',... 
                %             parent, 'FontSize', 9, 'Position', [.1 .90 - (chan - 1) * (1/13) .2 1/28], 'Background', 'white', 'UserData', struct('hs', hs, 'chan', chan), 'Callback', @this.WFSelectorCB,'Enable','off');
                % this.Channel_Trig_selectors(hs, chan)= uicontrol('Style', 'popupmenu', 'String', {'PC Trigger', 'External Trigger'}, 'Units', 'normalized', 'Parent',... 
                %             parent, 'FontSize', 9, 'Position', [.3 .90 - (chan - 1) * (1/13) .2 1/28], 'Background', 'white', 'UserData', struct('hs', hs, 'chan', chan), 'UserData', struct('hs', hs, 'chan', chan),...
                %             'Callback', @this.TrigSelectorCB,'Enable','off');
                this.toggle_button(hs, chan) = uicontrol('Style', 'togglebutton', 'String', 'Continuous Stream', 'Units', 'normalized', 'Parent', parent, 'UserData', struct('hs', hs, 'chan', chan),... 
                            'Position', [.2 .901 - (chan - 1) * (1/13) .25 1/28], 'Backgroundcolor',[.5 .5 .5], 'UserData', struct('hs', hs, 'chan', chan), 'Callback', @this.ContinuousButtonCB,'Enable','off');
                
                this.push_button (hs, chan) = uicontrol('Style', 'pushbutton', 'String', ['Trigger Channel  ', num2str(chan)], 'Units', 'normalized', 'Callback', @this.TriggerCallback, 'Parent',... 
                            parent, 'Position', [.5 .9002 - (chan - 1) * (1/13) .25 1/27.5], 'UserData', struct('Headstage', hs, 'Channel', chan), 'Enable','off');
                                    
                if mod(chan, 3) == 1
                    set(LED(chan),'Backgroundcolor',[135/255 206/255 250/255]);
                else
                    if mod(chan, 3) == 2
                    set(LED(chan),'Backgroundcolor',[100/255 149/255 237/255]);
                    else
                        set(LED(chan),'Backgroundcolor',[70/255 130/255 180/255]);
                    end
                end
            end
            
            for shank = 1:4
                subpanel(shank) = uipanel(this.f,'Position',[.402 0.899 - 0.1765 * shank .02 .148]);
                ax(shank) = axes('Parent',subpanel(shank),'Position',[0 0 0.45 0.28],'Visible','off');
                uistack(subpanel(shank),'top');                
                text(1,1,strcat(' Shank ', num2str(shank)),'Parent',ax(shank),'Rotation',90);
            end
           
        end
        
        % function WFSelectorCB(this, source, eventdata)
        %     this.os.UpdateChannelWaveform(source.UserData.hs, source.UserData.chan, get(source, 'Value'));
        %     this.ThrowException();
        % end
        
        % function TrigSelectorCB(this, source, eventdata)
        %     this.os.UpdateChannelTriggerType(source.UserData.hs, source.UserData.chan, get(source, 'Value') - 1);
        %     this.ThrowException();
        % end
        
        function ContinuousButtonCB(this, source, eventdata)
            state = get(source, 'Value');
            if state == get(source, 'Max')

            	this.os.TriggerPipe(source.UserData.chan, 0, 1, this.pipe_data)
               % if(this.os.Channels((source.UserData.hs - 1) * 12 + source.UserData.chan, 1) == 1)
               %    this.os.UpdateChannelPipeWf(source.UserData.hs, source.UserData.chan, 0);
               %    this.os.UpdatePipeInfo(numel(this.pipe_data), 65535);
               %    this.os.TriggerPipe(source.UserData.hs, source.UserData.chan, this.pipe_data);
               % else
               %    this.os.ToggleContinuous(source.UserData.hs, source.UserData.chan, 1);
               % end
               set(source, 'Background', 'g');
            else
            	% this.os.TriggerPipe(source.UserData.chan, 0, 0, this.pipe_data)
            	num_of_pulses = 0
            	this.os.WriteToWireIn(hex2dec('16'), 0, 16, num_of_pulses);
               % if(this.os.Channels((source.UserData.hs - 1) * 12 + source.UserData.chan, 1) == 1)
               %    this.os.UpdatePipeInfo(numel(this.pipe_data), 0);
               % else
               %    this.os.ToggleContinuous(source.UserData.hs, source.UserData.chan, 0);
               % end
               set(source, 'Backgroundcolor',[.5 .5 .5]);
            end
            this.ThrowException();
        end
        
        function CreateSetup(this)
            setup_panel = uipanel('Title', 'Setup', 'FontSize', 12, 'BackgroundColor', 'white', 'Units', 'normalized',...
                'Position', [.05 .78 .34 .17], 'Parent', this.f);
            hbutton = uicontrol('Style','pushbutton','String','Connect & Configure','Units', 'normalized', 'Position',[.55 .65 .4 .3],'Callback',@this.ConnectCallback, 'Parent', setup_panel);
            align(hbutton,'Center','None');
            this.load_parameter_button = uicontrol('Style','pushbutton','String','Load Parameters from File','Units', 'normalized', 'Position',[.06 .08 .25 .35],...
                'Callback',@this.LoadParameterCallback, 'Parent', setup_panel,'Enable','off');
            align(this.load_parameter_button,'Center','None');
            this.save_parameter_button = uicontrol('Style','pushbutton','String','Save Parameters To File','Units', 'normalized', 'Position',[.37 .08 .25 .35],...
                'Callback',@this.SaveParameterCallback, 'Parent', setup_panel,'Enable','off');
            align(this.save_parameter_button,'Center','None');
            
            this.pipe_button = uicontrol('Style','pushbutton','String','Custom waveform','Units', 'normalized', 'Position',[.67 .08 .25 .35],...
                'Callback',@this.PipeCallback, 'Parent', setup_panel,'Enable','off');
            align(this.pipe_button,'Center','None');
            
            this.serial_selector = uicontrol('Style', 'popupmenu', 'String', this.os.GetBoardSerials(), 'Units', 'normalized', 'Parent',... 
                            setup_panel, 'Position', [.05 .65 .4 .2], 'Background', 'white','Enable','on');
                 
            uicontrol('Style', 'text', 'String', 'Select your OSC136H Opal Kelly Serial', 'Units', 'normalized', 'Parent',...
                setup_panel, 'Position', [.05, .90, .4, .1], 'Background' , 'White')
                        
            this.reset = uicontrol('Style','pushbutton','String','Reset','Units', 'normalized', 'Position',[.05 .15 .1 .05],'Callback',@this.ResetCallback,...
                'Parent', this.f, 'Enable','off');
            align(this.reset,'Center','None');
                        
            exit = uicontrol('Style','pushbutton','String','Exit','Units', 'normalized', 'Position',[.25 .15 .1 .05],'Callback',@this.ExitCallback,...
                'Parent', this.f, 'Enable','on');
            align(exit,'Center','None');             
        end
        
        function ResetCallback(this, source, eventdata)
            ec = this.os.SysReset();
            if ec == 0
               this.UpdateParamDisplay();
            end
            this.ThrowException();
        end
        
        function ExitCallback(this, source, eventdata)
            if(ishandle(this.pipe_f))
                this.pipe_f.Visible = 'off';
            end
            this.f.Visible = 'off';
            this.delete();
        end
        
        function PipeCallback(this, source, eventdata)
            this.pipe_f.Visible = 'on';
            this.CreatePipePanel();
            this.ThrowException();
        end
        
        function PipePulseUpdate(this, source, eventdata)
            val = get(source, 'String');
            num = str2double(val);
            if ~isnan(num) && num >= 0 && num <= 8192
                this.temp_num_pipe_pulse = num;
            else
               errordlg('Please enter positive numeric values [0, 8192] for number of pulses.', 'Type Error');
            end
        end
        
        function LoadPipeCallback(this, source, eventdata)
          [txtfile, path] = uigetfile('*.cwave', 'Select the .cwave file');
           if ~isequal(txtfile, 0)
               try
               this.temp_pipe_data = this.os.SavePipeFromFile(strcat(path, txtfile));
               catch
                  errordlg('File error.', 'Type Error');
               end
           end 
        end
        
        function SavePipeCallback(this, source, eventdata)
            try
            SIZE = numel(this.temp_pipe_data);
                if (SIZE <= 1 || SIZE > 32768)
                    errordlg('Error: Invalid pipe data size. Valid size is [2, 32768]. No changes will be applied.', 'Type Error');
                    return
                end
            catch
                errordlg('Error: Invalid pipe data size. Valid size is [2, 32768]. No changes will be applied.', 'Type Error');
            end
            this.num_pipe_pulse = this.temp_num_pipe_pulse;
            this.pipe_data = this.temp_pipe_data;
            this.pipe_f.Visible = 'off';
            fprintf("Custom waveform initilization saved.\n");
            this.ThrowException();
        end
        
        function CancelPipeCallback(this, source, eventdata)
            this.temp_num_pipe_pulse = this.num_pipe_pulse;
            this.temp_pipe_data = this.pipe_data;
            this.pipe_f.Visible = 'off';
            fprintf("Custom waveform initilization canceled. No changes will be applied.\n");
        end
        
        function PreviewPipeCallback(this, source, eventdata)           
            data_size = numel(this.temp_pipe_data);
            x = 0:0.01:(data_size - 0.01);
            y = 0:0.01:(data_size - 0.01);
            for i = 1 : numel(x)
                y(i) = this.temp_pipe_data(floor(x(i)) + 1);
                x(i) = 0.0909 * x(i);
            end
            figure('Name','Preview of Pipe Waveform','numbertitle', 'off')
            plot(x,y);
            xlabel('Time (?s)') % x-axis label
            ylabel('Amplitude (?A)') % y-axis label
            if(this.temp_num_pipe_pulse >= 0)
                title(strcat({'The following pattern will repeat  '},num2str(this.temp_num_pipe_pulse),{'  times.'}));  
            end
            axis([0 (data_size - 0.01)*0.0909 -1 max(max(this.temp_pipe_data))+1 ]);
        end
        
        function CreatePipePanel(this)           
            pipe_text_panel = uipanel('Title', 'Instruction', 'FontSize', 12, 'BackgroundColor', 'white', 'Units', 'normalized',...
                'Position', [.045 .54 .43 .455], 'Parent', this.pipe_f);  

            intro_string = {'Custom waveform will assign a series of pre-defined amplitudes on each of the sampling time when it is triggered.',' ',...
                'The minimum step size in time is ~90 ?s (11kHz)','The maximum period of waveform is 32768 samples, i.e. ~2.98 s',' '...
                'To define the custom waveform:','Step 1: Type in the number of pulses', ...
                'Step 2: Input a .cwave file, which contains one number to represent the amplitude [0 - 1023] for each sampling. The number of lines in .cwave will reflect the full period of the custom waveform. The .cwave file can be generated by write2file.m',...
                'Step 3: (Optional) Preview the waveform','Step 4: Save the data and Exit', 'Step 5: Select custom waveform mode and trigger on a certain channel',' ','Click Cancel to exit without saving','WARNING: Discrete current changes may cause detectable artifacts in your recording signal. Please test in saline before use.'};

            uicontrol('Style', 'text', 'FontSize', 10, 'String', intro_string, 'Units', 'normalized', 'Parent',... 
                            pipe_text_panel, 'Position',[0.05 0.05 0.9 0.9], 'Background', 'white','horizontalalignment','left');
                
            pipe_setup1_panel = uipanel('Title', 'Step 1', 'FontSize', 12, 'BackgroundColor', 'white', 'Units', 'normalized',...
                'Position', [.57 .78 .34 .17], 'Parent', this.pipe_f);
            
            uicontrol('Style', 'text', 'FontSize', 10, 'String', 'Number of Pulses', 'Units', 'normalized', 'Parent',... 
                            pipe_setup1_panel, 'Position', [-0.12 .22 .6 .45], 'Background', 'white');
            uicontrol('Style', 'edit', 'String', num2str(this.temp_num_pipe_pulse), 'Units', 'normalized', 'Parent',... 
                pipe_setup1_panel, 'Position', [.45 .37 .32 .32], 'Background', 'white', 'Callback', @this.PipePulseUpdate);
            
            pipe_setup2_panel = uipanel('Title', 'Step 2', 'FontSize', 12, 'BackgroundColor', 'white', 'Units', 'normalized',...
                'Position', [.57 .53 .34 .19], 'Parent', this.pipe_f);
            uicontrol('Style','pushbutton','String','Load custom waveform','Units', 'normalized', 'Position',[.3 .35 .4 .4],...
                'Callback',@this.LoadPipeCallback, 'Parent', pipe_setup2_panel);
            
            pipe_setup3_panel = uipanel('Title', 'Step 3 (Optional)', 'FontSize', 12, 'BackgroundColor', 'white', 'Units', 'normalized',...
                'Position', [.57 .28 .34 .19], 'Parent', this.pipe_f);
            uicontrol('Style','pushbutton','String','Preview the custom waveform','Units', 'normalized', 'Position',[.3 .35 .4 .4],...
                'Callback',@this.PreviewPipeCallback, 'Parent', pipe_setup3_panel);
            
            savepipe_button = uicontrol('Style','pushbutton','String','Save & Exit', 'FontSize', 10, 'Units', 'normalized', 'Position',[.57 .11 .15 .08],'Callback',@this.SavePipeCallback,...
                'Parent', this.pipe_f,'Background', 'g');
            align(savepipe_button,'Center','None');
            
            cancel_button = uicontrol('Style','pushbutton','String','Cancel', 'FontSize', 10, 'Units', 'normalized', 'Position',[.77 .11 .15 .08],'Callback',@this.CancelPipeCallback,...
                'Parent', this.pipe_f,'Background', 'r');
            align(cancel_button,'Center','None');
            
            ax1 = axes('units','normalized','Parent',this.pipe_f,'position',[0.045 0.078 0.447 0.447],'Visible','off');          
%             myImage = imread('cus_waveform_inst.jpg');
            axes(ax1);
%             imshow(myImage);
        end
        
        function SaveParameterCallback(this, source, eventdata)
            [filename, path] = uiputfile('*.txt', 'Name Configuration File to Save');
            if ~isequal(filename, 0)
               this.os.SaveBoardToConfigFile(strcat(path, filename));
            end
            this.ThrowException();
        end
        
        function LoadParameterCallback(this, source, eventdata)
            [config_file, path] = uigetfile('*.txt', 'Select configuration txt file');
            if ~isequal(config_file, 0)
               this.os.InitBoardFromConfigFile(strcat(path, config_file));
               this.UpdateParamDisplay();
            end
            this.ThrowException();
        end
        
        function UpdateParamDisplay(this)
            for hs = 1:3
               for chan = 1:12
                  set(this.Channel_WF_selectors(hs,chan), 'Value', this.os.Channels((hs-1) * 12 + chan, 3));
                  set(this.Channel_Trig_selectors(hs,chan), 'Value', this.os.Channels((hs-1) * 12 + chan, 2) + 1);
               end
            end
            for wf = 1:4
                set(this.WF_pulse_selectors(wf), 'String', num2str(this.os.Waveforms(wf, 1))); 
                set(this.WF_amp_selectors(wf), 'String', num2str(this.os.Waveforms(wf, 2)));
                set(this.WF_pw_selectors(wf), 'String', num2str(this.os.Waveforms(wf, 3)));
                set(this.WF_period_selectors(wf), 'String', num2str(this.os.Waveforms(wf, 4)));
            end
        end
        
        function CreateWaveformPanels(this)
            % for wf = 1:4
            wf = 1;
               wf_panel = uipanel('Title', 'Choose minimum time resolution:', 'FontSize', 12, 'BackgroundColor', 'white', 'Units', 'normalized',...
                  'Position', [.05 .60 - ((3 -1) * .15) .34 .45], 'Parent', this.f);
               this.PopulateWaveformPanels(wf_panel, wf);
            % end
        end
        
        function PopulateWaveformPanels(this, parent, wf)
            % uicontrol('Style', 'text', 'String', 'Selected your step size', 'Units', 'normalized', 'Parent',... 
            %     parent, 'Position', [.1 .25 .4 .3], 'Background', 'white');

			% set(0, 'DefaultUIControlFontSize', 10);

            bg = uibuttongroup('Visible','on',...
                  'Position',[0.1 0.1 .85 .85],...
                  'Parent', parent);

            this.radio_buttons = zeros(1, 4);

			this.radio_buttons(1) = uicontrol(bg,'Style','radiobutton',...
                  'String',('0.0025ms'),'FontSize', 15, ...
                  'Position',[10 200 150 60],...
                  'HandleVisibility','off', 'Callback', @this.radio_Callback, 'Enable','off');
              
			this.radio_buttons(2) = uicontrol(bg,'Style','radiobutton',...
                  'String',('0.01ms'),'FontSize', 15, ...
                  'Position',[10 150 150 60],...
                  'HandleVisibility','off', 'Callback', @this.radio_Callback, 'Enable','off');

			this.radio_buttons(3) = uicontrol(bg,'Style','radiobutton',...
                  'String',('0.05ms'),'FontSize', 15,...
                  'Position',[10 100 150 60],...
                  'HandleVisibility','off', 'Callback', @this.radio_Callback, 'Enable','off');

			this.radio_buttons(4) = uicontrol(bg,'Style','radiobutton',...
                  'String',('0.1ms'),'FontSize', 15,...
                  'Position',[10 50 150 60],...
                  'HandleVisibility','off', 'Callback', @this.radio_Callback, 'Enable','off');

            % uicontrol('Style', 'text', 'String', 'Amplitude (uA)', 'Units', 'normalized', 'Parent',... 
            %     parent, 'Position', [.6 .75 .2 .2], 'Background', 'white');
            % uicontrol('Style', 'text', 'String', 'Pulse Width(ms)', 'Units', 'normalized', 'Parent',... 
            %     parent, 'Position', [.1 .25 .2 .2], 'Background', 'white');
            % uicontrol('Style', 'text', 'String', 'Period(ms)', 'Units', 'normalized', 'Parent',... 
            %     parent, 'Position', [.6 .25 .2 .2], 'Background', 'white');
            
            % this.WF_pulse_selectors(wf) = uicontrol('Style', 'edit', 'String', '0', 'Units', 'normalized', 'Parent',... 
            %     parent, 'Position', [.1 .05 .2 .2], 'Background', 'white', 'UserData', struct('wf', wf), 'Callback', @this.PulseSelectCB,'Enable','off');
            % this.WF_amp_selectors(wf) = uicontrol('Style', 'edit', 'String', '0', 'Units', 'normalized', 'Parent',... 
            %     parent, 'Position', [.6 .55 .2 .2], 'Background', 'white', 'UserData', struct('wf', wf), 'Callback', @this.AmpSelectCB,'Enable','off');
            % this.WF_pw_selectors(wf) = uicontrol('Style', 'edit', 'String', '0', 'Units', 'normalized', 'Parent',... 
            %     parent, 'Position', [.1 .05 .2 .2], 'Background', 'white', 'UserData', struct('wf', wf), 'Callback', @this.PWSelectCB,'Enable','off');
            % this.WF_period_selectors(wf) = uicontrol('Style', 'edit', 'String', '0', 'Units', 'normalized', 'Parent',... 
            %     parent, 'Position', [.6 .05 .2 .2], 'Background', 'white', 'UserData', struct('wf', wf), 'Callback', @this.PeriodSelectCB,'Enable','off');
        end


        function radio_Callback(this, source, eventdata)
        	string = get(source,'String');
        	if strcmp(string, '0.01ms')
        		this.os.WriteToWireIn(hex2dec('17'), 0, 16, 1);
        	elseif strcmp(string, '0.05ms')
        		this.os.WriteToWireIn(hex2dec('17'), 0, 16, 2);
        	elseif strcmp(string, '0.1ms')
        		this.os.WriteToWireIn(hex2dec('17'), 0, 16, 3);
        	else
        		this.os.WriteToWireIn(hex2dec('17'), 0, 16, 0);
        	end
        end
        
        % function PulseSelectCB(this, source, eventdata)
        %     ec = 0;
        %     val = get(source, 'String');
        %     num = str2double(val);
        %     if ~isnan(num)
        %         ec = this.os.UpdateWaveformPulses(source.UserData.wf, num);
        %     end
        %     if isnan(num)
        %        errordlg('Please enter only numeric values for number of pulses.', 'Type Error');
        %        this.UpdateParamDisplay();
        %     end
        %     if ec == -1
        %        errordlg('Invalid value for num pulses, valid values integers in range 0 to 63', 'Num Pulses Range Error');
        %        this.UpdateParamDisplay();
        %     end
        %     this.ThrowException();
        % end
        
        % function AmpSelectCB(this, source, eventdata)
        %     ec = 0;
        %     val = get(source, 'String');
        %     num = str2double(val);
        %     if ~isnan(num)
        %         ec = this.os.UpdateWaveformAmplitude(source.UserData.wf, num);
        %     end
        %     if isnan(num)
        %        errordlg('Please enter only numeric values for amplitude.', 'Type Error');
        %        this.UpdateParamDisplay();
        %     end
        %     if ec == -1
        %        errordlg('Invalid value for amplitude, valid values integers in range 0 to 1023 uA', 'Amplitude Range Error');
        %        this.UpdateParamDisplay();
        %     end
        %     this.ThrowException();
        % end
        
        % function PWSelectCB(this,source, eventdata)
        %     ec = 0;
        %     val = get(source, 'String');
        %     num = str2double(val);
        %     if ~isnan(num)
        %         ec = this.os.UpdateWaveformPulseWidth(source.UserData.wf, num);
        %     end
        %     if isnan(num)
        %        errordlg('Please enter only numeric values for pulse width.', 'Type Error');
        %        this.UpdateParamDisplay();
        %     end
        %     if ec == -1
        %        errordlg('Invalid value for pulse width, valid values multiples of 2.5 in range 0 to 637.5 ms', 'Pulse Width Range Error');
        %        this.UpdateParamDisplay();
        %     end
        %     this.ThrowException();
        % end
        
        % function PeriodSelectCB(this, source, eventdata)
        %     ec = 0;
        %     val = get(source, 'String');
        %     num = str2double(val);
        %     if ~isnan(num)
        %         ec = this.os.UpdateWaveformPeriod(source.UserData.wf, num);
        %     end
        %     if ec == -1
        %        errordlg('Invalid value for period, valid values multiples of 5 in range 0 to 1275 ms', 'Period Range Error');
        %        this.UpdateParamDisplay();
        %     end
        %     if isnan(num)
        %        errordlg('Please enter only numeric values for period.', 'Type Error');
        %        this.UpdateParamDisplay();
        %     end
        %     this.ThrowException();
        % end
        
        function TriggerCallback(this, source, eventdata)
            % if(this.os.Channels((source.UserData.Headstage - 1) * 12 + source.UserData.Channel, 1) == 1)
            %     this.os.UpdateChannelPipeWf(source.UserData.Headstage, source.UserData.Channel, 0);
            %     this.os.UpdatePipeInfo(numel(this.pipe_data), this.num_pipe_pulse);
                % this.os.TriggerPipe(source.UserData.Headstage, source.UserData.Channel, this.pipe_data);
            this.os.TriggerPipe(source.UserData.Channel, this.num_pipe_pulse, 0, this.pipe_data)
            % else
            %     this.os.TriggerChannel(source.UserData.Headstage, source.UserData.Channel);
            % end
            this.ThrowException();
        end
        
        function UpdateEnable(this)
             set(this.toggle_button,'Enable','on');
             set(this.push_button,'Enable','on');
             % set(this.Channel_WF_selectors,'Enable','on');
             % set(this.Channel_Trig_selectors,'Enable','on');
             % set(this.WF_pulse_selectors,'Enable','on');
             % set(this.WF_period_selectors,'Enable','on');
             % set(this.WF_amp_selectors,'Enable','on');
             % set(this.WF_pw_selectors,'Enable','on');
             set(this.load_parameter_button,'Enable','on');
             set(this.save_parameter_button,'Enable','on');
             set(this.pipe_button,'Enable','on');
             set(this.reset,'Enable','on');
             set(this.radio_buttons,'Enable','on');
        end
        
        function ConnectCallback(this, source, eventdata)
            if source.String == "Connect & Configure"
                contents = get(this.serial_selector, 'String');
                serial_string = contents(get(this.serial_selector, 'Value'),:);
                ec = this.os.Connect(serial_string);
                if ec == 0
                       [bitfile, path] = uigetfile('*.bit', 'Select the control bitfile');
                       if ~isequal(bitfile, 0)
                           this.os.Configure(strcat(path, bitfile));
				            pause(1);
				            if this.os.SysReset() == -1 || this.os.SetControlReg() == -1
				            	fprintf('Failed to initialize.\n')
				            	return
				            end
        					this.os.WriteToWireIn(hex2dec('17'), 0, 16, 0);
				            fprintf('Successfully connected and configured.\n')
                            set(source, 'String', 'Disconnect');
                            this.connected = 1;
                            this.connected_serial_name = serial_string;
                            this.UpdateEnable();

                       else
                           this.os.Disconnect();
                           this.connected = 0; 
                           this.connected_serial_name = 'No connected devices';
                           this.DetectBoard();
                       end
                end
             else
                     ec = this.os.Disconnect();
                        if ec == 0
                        this.os = OSC136H();
                        this.ResetGUIdisplay();
                        this.DetectBoard();
                        end
             end
        end
        
        

    end
end